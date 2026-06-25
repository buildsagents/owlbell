"""
tasks.py -- Celery task definitions for the orchestration layer.

Defines all async background tasks:
- process_audio_chunk: STT transcription of audio chunk
- generate_response: LLM response generation
- synthesize_speech: TTS audio synthesis
- handle_call_end: Call cleanup and archiving
- send_call_summary: Post-call summary notification
- sync_calendar_events: Periodic calendar synchronization

All AI tasks are routed to the 'ai' queue for GPU workers.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import random
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from celery import Task, shared_task
    from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded

    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

    # Stub classes for when Celery is not installed
    class Task:  # type: ignore
        """Stub Task base class."""

        pass

    def shared_task(*args, **kwargs):  # type: ignore
        """Stub shared_task decorator."""

        def decorator(func):
            return func

        return decorator

logger = logging.getLogger(__name__)


# ---- Task Options ----
# All AI tasks use the 'ai' queue, routed to GPU workers
# Routing config in celeryconfig.py:
# task_routes = {'orchestrator.tasks.ai_*': {'queue': 'ai'}}


class AIBaseTask(Task):
    """Base task with common AI task behavior."""

    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 60
    retry_kwargs = {"max_retries": 3}
    soft_time_limit = 30
    time_limit = 60

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure - publish event and update session."""
        call_id = kwargs.get("call_id") or (args[0] if args else None)
        if call_id:
            try:
                from orchestrator.event_bus import EventBus
                from orchestrator.models import EventType, SystemEvent

                event_bus = EventBus()
                event_bus.publish(
                    SystemEvent(
                        event_type=EventType.ERROR_WORKER_CRASH,
                        call_id=call_id,
                        worker_id=getattr(self.request, "hostname", "unknown"),
                        payload={
                            "error": str(exc),
                            "task_id": task_id,
                            "task_name": self.name,
                        },
                    )
                )
            except Exception as e:
                logger.error(f"Failed to publish failure event: {e}")
        super().on_failure(exc, task_id, args, kwargs, einfo)


# ---- STT Task ----


@shared_task(
    base=AIBaseTask if CELERY_AVAILABLE else Task,
    bind=True,
    name="orchestrator.tasks.ai_stt",
)
def ai_stt(
    self,
    call_id: str,
    audio_b64: str,
    audio_format: str = "pcm_s16le_16k",
) -> Dict[str, Any]:
    """Transcribe audio chunk using Whisper.

    Args:
        call_id: Session identifier
        audio_b64: Base64-encoded PCM audio data
        audio_format: Audio format descriptor

    Returns:
        Dict with transcribed text, confidence, language, timing

    Raises:
        SoftTimeLimitExceeded: If processing takes > 30s
    """
    start_time = time.time()

    try:
        from orchestrator.models import CallState
        from orchestrator.session_manager import SessionManager

        # Update session state
        session_mgr = SessionManager()
        session = session_mgr.get_session(call_id)
        if session:
            session_mgr.update_session(
                call_id,
                {
                    "state": CallState.PROCESSING,
                    "stt_calls": session.stt_calls + 1,
                },
            )

        # Decode audio
        audio_bytes = base64.b64decode(audio_b64)

        async def _do_stt() -> Dict[str, Any]:
            from backend.ai.stt.whisper_service import get_whisper_service

            svc = await get_whisper_service()
            stt = await svc.transcribe(audio_bytes)
            return {
                "text": stt.text,
                "confidence": stt.confidence,
                "language": stt.language,
                "is_partial": stt.is_partial,
                "processing_time_ms": stt.processing_time_ms,
            }

        result = asyncio.run(_do_stt())

        processing_time_ms = result.get("processing_time_ms", int((time.time() - start_time) * 1000))

        # Update session back to active
        if session:
            session_mgr.update_session(
                call_id,
                {
                    "state": CallState.ACTIVE,
                    "last_activity_at": datetime.utcnow(),
                },
            )

        return {
            "text": result["text"],
            "confidence": result.get("confidence", 0.0),
            "language": result.get("language", "en"),
            "is_partial": result.get("is_partial", False),
            "processing_time_ms": processing_time_ms,
        }

    except Exception as exc:
        logger.error(f"STT task failed for call {call_id}: {exc}")
        raise


# ---- LLM Task ----


@shared_task(
    base=AIBaseTask if CELERY_AVAILABLE else Task,
    bind=True,
    name="orchestrator.tasks.ai_llm",
    soft_time_limit=15,
    time_limit=30,
)
def ai_llm(
    self,
    call_id: str,
    transcript: list,
    agent_config: dict,
    context: Optional[dict] = None,
) -> Dict[str, Any]:
    """Generate AI response using LLM.

    Uses circuit breaker to fail fast if LLM is overloaded.

    Args:
        call_id: Session identifier
        transcript: Full conversation transcript
        agent_config: Business-specific agent configuration
        context: Additional context (CRM data, KB articles, etc.)

    Returns:
        Dict with response text, actions, timing
    """
    from orchestrator.circuit_breaker import get_circuit_breaker
    from orchestrator.models import CallState
    from orchestrator.session_manager import SessionManager

    start_time = time.time()

    # Check circuit breaker
    cb = get_circuit_breaker("llm")
    if cb.current_state == "open":
        return {
            "text": _get_fallback_response(agent_config),
            "actions": [],
            "processing_time_ms": 10,
            "from_cache": True,
            "circuit_open": True,
        }

    session_mgr = SessionManager()
    session = session_mgr.get_session(call_id)
    if session:
        session_mgr.update_session(
            call_id,
            {
                "state": CallState.PROCESSING,
                "llm_calls": session.llm_calls + 1,
            },
        )

    try:
        with cb.sync_call():

            async def _do_llm() -> Dict[str, Any]:
                from backend.ai.llm.ollama_client import get_ollama_client

                client = await get_ollama_client()

                business_context = {
                    "name": agent_config.get("agent_name", "the business"),
                    "type": agent_config.get("business_type", "generic"),
                    "agent_id": agent_config.get("agent_id", ""),
                }
                system_prompt = client.build_system_prompt(business_context)

                messages = [{"role": "system", "content": system_prompt}]
                for entry in transcript:
                    role = (
                        "user"
                        if entry.get("speaker") == "caller"
                        else "assistant"
                    )
                    messages.append(
                        {"role": role, "content": entry.get("text", "")}
                    )

                llm = await client.chat(messages)
                return {
                    "text": llm.content,
                    "actions": [
                        {"type": tc.get("function", {}).get("name", "unknown"), "params": tc.get("function", {}).get("arguments", {})}
                        for tc in llm.tool_calls
                    ],
                    "processing_time_ms": llm.latency_ms,
                }

            result = asyncio.run(_do_llm())

        cb.record_sync_success()

        processing_time_ms = result.get("processing_time_ms", int((time.time() - start_time) * 1000))

        if session:
            session_mgr.update_session(
                call_id, {"state": CallState.ACTIVE}
            )

        return {
            "text": result["text"],
            "actions": result.get("actions", []),
            "processing_time_ms": processing_time_ms,
            "from_cache": False,
        }

    except Exception as e:
        cb.record_sync_failure()
        logger.error(f"LLM task failed for call {call_id}: {e}")
        raise self.retry(exc=e, countdown=2)


# ---- TTS Task ----


@shared_task(
    base=AIBaseTask if CELERY_AVAILABLE else Task,
    bind=True,
    name="orchestrator.tasks.ai_tts",
    soft_time_limit=10,
    time_limit=20,
)
def ai_tts(
    self,
    call_id: str,
    text: str,
    voice_id: Optional[str] = None,
    speed: float = 1.0,
) -> Dict[str, Any]:
    """Synthesize speech using TTS.

    Args:
        call_id: Session identifier
        text: Text to synthesize
        voice_id: Voice identifier (per-tenant or default)
        speed: Speech speed multiplier

    Returns:
        Dict with audio_b64, duration_ms, format
    """
    start_time = time.time()

    try:
        from orchestrator.session_manager import SessionManager

        session_mgr = SessionManager()
        session = session_mgr.get_session(call_id)
        if session:
            session_mgr.update_session(
                call_id,
                {"tts_calls": session.tts_calls + 1},
            )

        async def _do_tts() -> Dict[str, Any]:
            from backend.ai.tts.piper_service import get_piper_service

            svc = await get_piper_service()
            tts = await svc.synthesize(
                text,
                voice=voice_id,
                speed=speed,
                sample_rate=16000,
            )
            pcm_bytes = tts.pcm16.tobytes()
            return {
                "audio_b64": base64.b64encode(pcm_bytes).decode("utf-8"),
                "duration_ms": tts.duration_ms,
                "processing_time_ms": tts.processing_time_ms,
            }

        result = asyncio.run(_do_tts())

        actual_duration_ms = result["duration_ms"]
        processing_time_ms = result["processing_time_ms"]
        audio_bytes = base64.b64decode(result["audio_b64"])

        return {
            "audio_b64": base64.b64encode(audio_bytes).decode("utf-8"),
            "duration_ms": actual_duration_ms,
            "processing_time_ms": processing_time_ms,
            "format": "pcm_s16le_16k",
        }

    except Exception as exc:
        logger.error(f"TTS task failed for call {call_id}: {exc}")
        raise


# ---- End-to-End Pipeline Task ----


@shared_task(
    base=AIBaseTask if CELERY_AVAILABLE else Task,
    bind=True,
    name="orchestrator.tasks.ai_pipeline",
    soft_time_limit=25,
    time_limit=45,
)
def ai_pipeline(
    self,
    call_id: str,
    audio_b64: str,
    audio_format: str = "pcm_s16le_16k",
) -> Dict[str, Any]:
    """Full AI pipeline: STT -> LLM -> TTS in a single Celery task.

    This is the primary task for real-time call processing.
    All sub-tasks run synchronously within this task to minimize latency.

    Args:
        call_id: Session identifier
        audio_b64: Base64-encoded caller audio
        audio_format: Audio format

    Returns:
        Dict with response_audio_b64, transcript, response_text, timing
    """
    total_start = time.time()
    breakdown: Dict[str, int] = {}

    try:
        from orchestrator.event_bus import EventBus
        from orchestrator.models import CallState, EventType, SystemEvent
        from orchestrator.session_manager import SessionManager

        session_mgr = SessionManager()
        event_bus = EventBus()
        session = session_mgr.get_session(call_id)
        if not session:
            raise ValueError(f"Session {call_id} not found")

        # ---- Pipeline: STT -> LLM -> TTS (single async context) ----
        audio_bytes = base64.b64decode(audio_b64)
        stt_start = time.time()

        async def _run_pipeline():
            from backend.ai.llm.ollama_client import get_ollama_client
            from backend.ai.tts.piper_service import get_piper_service
            from backend.ai.stt.whisper_service import get_whisper_service

            # STT
            stt_svc = await get_whisper_service()
            stt_result = await stt_svc.transcribe(audio_bytes)

            stt_ms = int((time.time() - stt_start) * 1000)

            transcript_text = stt_result.text.strip()
            if not transcript_text:
                return {
                    "response_audio_b64": "",
                    "transcript": "",
                    "response_text": "",
                    "total_latency_ms": stt_ms,
                    "breakdown": {"stt_ms": stt_ms},
                }

            # Update transcript with caller input
            new_entry = {
                "speaker": "caller",
                "text": transcript_text,
                "timestamp": datetime.utcnow().isoformat(),
            }
            updated_transcript = session.transcript + [new_entry]
            session_mgr.update_session(
                call_id,
                {
                    "transcript": updated_transcript,
                    "stt_calls": session.stt_calls + 1,
                },
            )

            event_bus.publish(
                SystemEvent(
                    event_type=EventType.TRANSCRIPT_READY,
                    call_id=call_id,
                    tenant_id=session.tenant_id,
                    payload={"speaker": "caller", "text": transcript_text},
                )
            )

            # LLM
            llm_start = time.time()
            llm_client = await get_ollama_client()

            business_context = {
                "name": session.agent_name or "the business",
                "type": session.agent_config.get("business_type", "generic"),
                "agent_id": session.agent_id,
            }
            system_prompt = llm_client.build_system_prompt(business_context)

            messages = [{"role": "system", "content": system_prompt}]
            for entry in updated_transcript:
                role = "user" if entry.get("speaker") == "caller" else "assistant"
                messages.append({"role": role, "content": entry.get("text", "")})

            llm_result = await llm_client.chat(messages)

            llm_ms = int((time.time() - llm_start) * 1000)
            llm_text = llm_result.content
            actions = [
                {
                    "type": tc.get("function", {}).get("name", "unknown"),
                    "params": tc.get("function", {}).get("arguments", {}),
                }
                for tc in llm_result.tool_calls
            ]

            # Update session with AI response
            ai_entry = {
                "speaker": "agent",
                "text": llm_text,
                "timestamp": datetime.utcnow().isoformat(),
            }
            updated_transcript.append(ai_entry)
            session_mgr.update_session(
                call_id,
                {
                    "transcript": updated_transcript,
                    "llm_calls": session.llm_calls + 1,
                    "current_utterance": llm_text,
                },
            )

            event_bus.publish(
                SystemEvent(
                    event_type=EventType.LLM_RESPONSE_READY,
                    call_id=call_id,
                    tenant_id=session.tenant_id,
                    payload={"text": llm_text[:200], "actions": actions},
                )
            )

            # TTS
            tts_start_local = time.time()
            tts_svc = await get_piper_service()
            tts_result = await tts_svc.synthesize(
                llm_text,
                speed=1.0,
                sample_rate=16000,
            )

            tts_ms = int((time.time() - tts_start_local) * 1000)
            audio_response = tts_result.pcm16.tobytes()

            return {
                "transcript_text": transcript_text,
                "llm_text": llm_text,
                "actions": actions,
                "audio_response": audio_response,
                "stt_ms": stt_ms,
                "llm_ms": llm_ms,
                "tts_ms": tts_ms,
                "response_duration_ms": tts_result.duration_ms,
                "updated_transcript": updated_transcript,
            }

        pipeline_result = asyncio.run(_run_pipeline())

        if "total_latency_ms" in pipeline_result:
            return pipeline_result

        breakdown["stt_ms"] = pipeline_result["stt_ms"]
        breakdown["llm_ms"] = pipeline_result["llm_ms"]
        breakdown["tts_ms"] = pipeline_result["tts_ms"]
        transcript_text = pipeline_result["transcript_text"]
        llm_text = pipeline_result["llm_text"]
        actions = pipeline_result["actions"]
        audio_response = pipeline_result["audio_response"]

        response_duration_ms = int(len(audio_response) / 32)
        session_mgr.update_session(
            call_id,
            {
                "tts_calls": session.tts_calls + 1,
                "total_audio_seconds": (
                    session.total_audio_seconds + (response_duration_ms / 1000)
                ),
            },
        )

        event_bus.publish(
            SystemEvent(
                event_type=EventType.TTS_AUDIO_READY,
                call_id=call_id,
                tenant_id=session.tenant_id,
                payload={"duration_ms": response_duration_ms},
            )
        )

        total_ms = int((time.time() - total_start) * 1000)
        breakdown["overhead_ms"] = max(
            0, total_ms - sum(breakdown.values())
        )

        return {
            "response_audio_b64": base64.b64encode(audio_response).decode(
                "utf-8"
            ),
            "transcript": transcript_text,
            "response_text": llm_text,
            "actions": actions,
            "total_latency_ms": total_ms,
            "breakdown": breakdown,
        }

    except Exception as exc:
        logger.error(f"AI pipeline failed for call {call_id}: {exc}")
        raise


# ---- Session Cleanup Task ----


@shared_task(name="orchestrator.tasks.archive_session")
def archive_session(call_id: str) -> bool:
    """Move session from Redis to PostgreSQL for long-term storage.

    Called when call ends (state = ENDED).

    Args:
        call_id: Call identifier

    Returns:
        True if archived successfully
    """
    try:
        from orchestrator.session_manager import SessionManager

        session_mgr = SessionManager()
        session = session_mgr.get_session(call_id)
        if not session:
            return False

        async def _persist() -> bool:
            from backend.config import get_settings
            from backend.db.models.call import Call
            from backend.db.models.enums import CallDirection, CallStatus
            from sqlalchemy.ext.asyncio import (
                AsyncSession,
                async_sessionmaker,
                create_async_engine,
            )

            settings = get_settings()
            engine = create_async_engine(
                settings.database_url, echo=False, pool_pre_ping=True
            )
            maker = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )

            try:
                async with maker() as db_session:
                    duration = (
                        int((session.ended_at - session.answered_at).total_seconds())
                        if session.ended_at and session.answered_at
                        else None
                    )
                    record = Call(
                        id=uuid.uuid4(),
                        call_sid=session.call_id,
                        direction=CallDirection.INBOUND,
                        caller_number=session.caller_number,
                        caller_name=session.caller_name,
                        destination_number=session.phone_number,
                        status=(
                            CallStatus.COMPLETED
                            if session.state == "ended"
                            else CallStatus.ACTIVE
                        ),
                        started_at=session.created_at,
                        answered_at=session.answered_at,
                        ended_at=session.ended_at,
                        duration_seconds=duration,
                        talk_time_seconds=int(session.total_audio_seconds),
                        ai_handled=True,
                        error_count=session.error_count,
                        metadata_json={
                            "agent_id": session.agent_id,
                            "agent_name": session.agent_name,
                            "llm_calls": session.llm_calls,
                            "stt_calls": session.stt_calls,
                            "tts_calls": session.tts_calls,
                            "audio_chunks_received": session.audio_chunks_received,
                            "audio_chunks_sent": session.audio_chunks_sent,
                            "transcript": session.transcript,
                        },
                    )
                    db_session.add(record)
                    await db_session.commit()
                return True
            except Exception:
                raise
            finally:
                await engine.dispose()

        persisted = asyncio.run(_persist())
        if not persisted:
            return False

        # Clean up Redis
        session_mgr.delete_session(call_id)
        logger.info(f"Session archived: {call_id}")
        return True

    except Exception as exc:
        logger.error(f"Session archive failed for {call_id}: {exc}")
        return False


# ---- Health Check Task (periodic) ----


@shared_task(name="orchestrator.tasks.worker_health_sweep")
def worker_health_sweep() -> Dict[str, Any]:
    """Periodic task to check worker health and restart unhealthy workers.

    Runs every 10 seconds via Celery beat.

    Returns:
        Dict with health check results
    """
    # This is called synchronously; the async version would be used in practice
    return {
        "status": "scheduled",
        "message": "Health sweep should be run via async health_monitor.check_all_workers()",
    }


# ---- Queue Wait Time Estimation ----


@shared_task(name="orchestrator.tasks.update_queue_estimates")
def update_queue_estimates() -> Dict[str, Any]:
    """Update estimated wait times for all queued calls.

    Runs every 5 seconds via Celery beat.
    Uses exponential moving average of actual wait times.

    Returns:
        Dict with update statistics
    """
    return {"status": "scheduled", "message": "Use call_queue.update_all_estimates()"}


# ---- Call Summary Task ----


@shared_task(name="orchestrator.tasks.send_call_summary")
def send_call_summary(call_id: str) -> Dict[str, Any]:
    """Send call summary notification.

    Args:
        call_id: Call identifier

    Returns:
        Dict with send status
    """
    try:
        from orchestrator.session_manager import SessionManager

        session_mgr = SessionManager()
        session = session_mgr.get_session(call_id)
        if not session:
            return {"error": "Session not found"}

        async def _notify() -> Dict[str, Any]:
            from backend.integrations.twilio import send_sms as twilio_send_sms

            caller_turns = sum(
                1 for e in session.transcript if e.get("speaker") == "caller"
            )
            agent_turns = sum(
                1 for e in session.transcript if e.get("speaker") == "agent"
            )
            summary_lines = session.transcript[:10]

            excerpt = "\n".join(
                f"{e.get('speaker','?').upper()}: {e.get('text','')}"
                for e in summary_lines
            )
            sms_body = (
                f"Call Summary ({call_id[:8]}):\n"
                f"Exchanges: {len(session.transcript)} "
                f"(caller {caller_turns}, agent {agent_turns})\n"
                f"Duration: {session.total_audio_seconds:.0f}s\n"
                f"Excerpt:\n{excerpt}"
            )

            sms_result = await twilio_send_sms(
                to=session.caller_number,
                body=sms_body,
                tenant_id=session.tenant_id,
            )

            return {
                "call_id": call_id,
                "transcript_length": len(session.transcript),
                "llm_calls": session.llm_calls,
                "sms_status": sms_result.get("status", "unknown"),
                "status": "sent",
            }

        return asyncio.run(_notify())

    except Exception as exc:
        logger.error(f"Send summary failed for {call_id}: {exc}")
        return {"error": str(exc)}


# ---- Calendar Sync Task ----


@shared_task(name="orchestrator.tasks.sync_calendar_events")
def sync_calendar_events(tenant_id: str) -> Dict[str, Any]:
    """Sync calendar events for a tenant.

    Args:
        tenant_id: Tenant identifier

    Returns:
        Dict with sync status
    """
    try:
        async def _sync() -> int:
            from datetime import date, timedelta

            from backend.config import get_settings
            from backend.db.models.business import Appointment
            from sqlalchemy import select
            from sqlalchemy.ext.asyncio import (
                AsyncSession,
                async_sessionmaker,
                create_async_engine,
            )

            settings = get_settings()
            engine = create_async_engine(
                settings.database_url, echo=False, pool_pre_ping=True
            )
            maker = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )

            try:
                async with maker() as db_session:
                    today = date.today()
                    cutoff = today + timedelta(days=30)
                    result = await db_session.execute(
                        select(Appointment)
                        .where(
                            Appointment.tenant_id == tenant_id,
                            Appointment.scheduled_date >= today,
                            Appointment.scheduled_date <= cutoff,
                        )
                        .order_by(Appointment.scheduled_date, Appointment.start_time)
                    )
                    appointments = result.scalars().all()

                    for appt in appointments:
                        logger.info(
                            f"Appointment {appt.id}: "
                            f"{appt.scheduled_date}T{appt.start_time} - "
                            f"{appt.caller_name or 'unknown'} "
                            f"({appt.status.value})"
                        )

                    return len(appointments)
            finally:
                await engine.dispose()

        count = asyncio.run(_sync())

        logger.info(f"Calendar sync for tenant {tenant_id}: {count} events found")

        return {
            "tenant_id": tenant_id,
            "events_synced": count,
            "status": "completed",
        }

    except Exception as exc:
        logger.error(f"Calendar sync failed for tenant {tenant_id}: {exc}")
        return {"error": str(exc)}


# ---- Utility Functions ----


FALLBACK_RESPONSES = [
    "I'm sorry, I'm having a little trouble right now. Could you repeat that?",
    "I apologize for the delay. Let me try again.",
    "Thanks for your patience. I'm still here!",
]


def _get_fallback_response(agent_config: Dict[str, Any]) -> str:
    """Get a fallback response when AI services are degraded.

    Args:
        agent_config: Agent configuration with fallback_responses

    Returns:
        Fallback response string
    """
    fallbacks = agent_config.get("fallback_responses", FALLBACK_RESPONSES)
    return random.choice(fallbacks)


def determine_disposition(session: Any) -> str:
    """Determine call disposition for analytics.

    Args:
        session: Session object

    Returns:
        Disposition string
    """
    if session.error_count > 5:
        return "error"
    if session.ended_at and session.answered_at:
        duration = (session.ended_at - session.answered_at).total_seconds()
        if duration < 5:
            return "abandoned"
        return "completed"
    if not session.answered_at:
        return "missed"
    return "unknown"


def process_audio_chunk(call_id: str, audio_data: str) -> Any:
    """Process audio chunk wrapper for WorkerPool dispatch.

    Args:
        call_id: Session identifier
        audio_data: Base64-encoded audio

    Returns:
        Celery AsyncResult
    """
    return ai_pipeline.delay(call_id, audio_data)


def generate_response(call_id: str, transcript: list) -> Any:
    """Generate response wrapper for WorkerPool dispatch.

    Args:
        call_id: Session identifier
        transcript: Conversation transcript

    Returns:
        Celery AsyncResult
    """
    return ai_llm.delay(call_id, transcript, {})


def synthesize_speech(call_id: str, text: str) -> Any:
    """Synthesize speech wrapper for WorkerPool dispatch.

    Args:
        call_id: Session identifier
        text: Text to synthesize

    Returns:
        Celery AsyncResult
    """
    return ai_tts.delay(call_id, text)


def handle_call_end(call_id: str) -> Any:
    """Handle call end wrapper for WorkerPool dispatch.

    Args:
        call_id: Session identifier

    Returns:
        Celery AsyncResult
    """
    return archive_session.delay(call_id)


def send_call_summary_task(call_id: str) -> Any:
    """Send call summary wrapper for WorkerPool dispatch.

    Args:
        call_id: Session identifier

    Returns:
        Celery AsyncResult
    """
    return send_call_summary.delay(call_id)


def sync_calendar_events_task(tenant_id: str) -> Any:
    """Sync calendar events wrapper for WorkerPool dispatch.

    Args:
        tenant_id: Tenant identifier

    Returns:
        Celery AsyncResult
    """
    return sync_calendar_events.delay(tenant_id)
