"""
call_handler.py — Inbound call handler: bridges FreeSWITCH calls to the AI pipeline.

This is the brain that connects an incoming phone call to the AI conversation engine:

1. CHANNEL_CREATE: Detect incoming call → create orchestrator session → answer
2. Audio streaming: Bridge caller audio ↔ AI pipeline via WebSocket
3. AI conversation: STT (Whisper) → LLM (Ollama) → TTS (Piper) → playback to caller
4. DTMF/commands: Handle keypresses for transfer, hold, etc.
5. CHANNEL_HANGUP: Clean up session, trigger post-call processing

Integration Points:
- IN: ESLConnection (FreeSWITCH events)
- OUT: SessionManager (session lifecycle)
- OUT: EventBus (system events)
- OUT: AI Pipeline (Whisper STT, Ollama LLM, Piper TTS)
- OUT: ESLConnection (answer, playback, hangup commands)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

from backend.dependencies import get_session_maker
from telephony.core.esl_connection import ESLConnection, ESLEvent

logger = structlog.get_logger(__name__)


class CallHandler:
    """Handles the full lifecycle of inbound calls.

    Wiring:
        esl = ESLConnection(...)
        handler = CallHandler(esl, session_manager, event_bus, ai_pipeline, settings)
        handler.register()
        await esl.connect()
    """

    def __init__(
        self,
        esl: ESLConnection,
        session_manager: Any,
        event_bus: Any,
        ai_pipeline: Any,
        settings: Any,
    ):
        self.esl = esl
        self.session_mgr = session_manager
        self.event_bus = event_bus
        self.ai_pipeline = ai_pipeline
        self.settings = settings

        # Track active call processing tasks: call_id -> asyncio.Task
        self._call_tasks: Dict[str, asyncio.Task] = {}

        # Recording directory
        self.recording_dir = "/var/lib/freeswitch/recordings"

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register(self) -> None:
        """Register all event handlers with the ESL connection."""
        self.esl.on("CHANNEL_CREATE", self._on_channel_create)
        self.esl.on("CHANNEL_ANSWER", self._on_channel_answer)
        self.esl.on("CHANNEL_HANGUP", self._on_channel_hangup)
        self.esl.on("CHANNEL_HANGUP_COMPLETE", self._on_channel_hangup_complete)
        self.esl.on("DTMF", self._on_dtmf)
        self.esl.on("CUSTOM", self._on_custom_event)

        logger.info("call_handler.registered")

    # ------------------------------------------------------------------ #
    # Event handlers
    # ------------------------------------------------------------------ #

    async def _on_channel_create(self, event: ESLEvent) -> None:
        """Handle CHANNEL_CREATE — inbound call is ringing."""
        call_id = event.call_id
        caller_number = event.caller_number or "unknown"
        caller_name = event.caller_name or ""
        destination = event.destination_number or ""
        tenant_id = event.variable_tenant_id or await self._resolve_tenant(destination)

        if not call_id:
            logger.warning("call_handler.channel_create.no_call_id", event=event.headers)
            return

        logger.info(
            "call_handler.inbound_call",
            call_id=call_id,
            caller=caller_number,
            caller_name=caller_name,
            destination=destination,
            tenant_id=tenant_id,
        )

        # Create orchestrator session
        try:
            from orchestrator.models import ActiveSession, CallState, SystemEvent, EventType

            session = ActiveSession(
                call_id=call_id,
                tenant_id=tenant_id,
                caller_number=caller_number,
                caller_name=caller_name,
                destination_number=destination,
                state=CallState.CREATED,
                created_at=datetime.utcnow(),
                worker_id=None,
                audio_chunks_received=0,
                audio_chunks_sent=0,
                error_count=0,
                metadata={
                    "channel_state": event.channel_state,
                    "direction": "inbound",
                },
            )

            await self.session_mgr.create_session(session)

            # Publish event
            self.event_bus.publish(SystemEvent(
                event_type=EventType.CALL_STARTED,
                call_id=call_id,
                tenant_id=tenant_id,
                payload={
                    "caller_number": caller_number,
                    "caller_name": caller_name,
                    "destination_number": destination,
                    "channel_state": event.channel_state,
                },
            ))

            # Answer the call
            await self.esl.answer(call_id)

            logger.info("call_handler.answer_sent", call_id=call_id)

        except Exception as exc:
            logger.error("call_handler.create_session_failed", call_id=call_id, error=str(exc))

    async def _on_channel_answer(self, event: ESLEvent) -> None:
        """Handle CHANNEL_ANSWER — call is answered, start AI conversation."""
        call_id = event.call_id
        if not call_id:
            return

        logger.info("call_handler.answered", call_id=call_id)

        # Transition session to CONNECTING
        try:
            await self.session_mgr.update_session(call_id, {"state": "connecting"})
        except Exception:
            pass

        # Start the AI conversation task
        if call_id not in self._call_tasks:
            task = asyncio.create_task(self._run_conversation(call_id))
            self._call_tasks[call_id] = task

    async def _on_channel_hangup(self, event: ESLEvent) -> None:
        """Handle CHANNEL_HANGUP — caller hung up."""
        call_id = event.call_id
        if not call_id:
            return

        hangup_cause = event.hangup_cause or "unknown"
        logger.info("call_handler.hangup", call_id=call_id, cause=hangup_cause)

        await self._cleanup_call(call_id, hangup_cause)

    async def _on_channel_hangup_complete(self, event: ESLEvent) -> None:
        """Handle CHANNEL_HANGUP_COMPLETE — final cleanup."""
        call_id = event.call_id
        if not call_id:
            return

        # Ensure cleanup happened
        if call_id in self._call_tasks:
            await self._cleanup_call(call_id, event.hangup_cause or "completed")

    async def _on_dtmf(self, event: ESLEvent) -> None:
        """Handle DTMF keypresses."""
        call_id = event.call_id
        digit = event.get("DTMF-Digit")

        if not call_id or not digit:
            return

        logger.info("call_handler.dtmf", call_id=call_id, digit=digit)

        # Route DTMF: 0 = transfer to operator, 9 = repeat, etc.
        if digit == "0":
            await self._transfer_to_operator(call_id)
        elif digit == "9":
            # Repeat last AI response
            await self._repeat_last_response(call_id)

    async def _on_custom_event(self, event: ESLEvent) -> None:
        """Handle custom FreeSWITCH events."""
        subclass = event.get("Event-Subclass", "")
        if subclass == "audio_stream::start":
            logger.debug("call_handler.audio_stream_start", call_id=event.call_id)
        elif subclass == "audio_stream::stop":
            logger.debug("call_handler.audio_stream_stop", call_id=event.call_id)

    # ------------------------------------------------------------------ #
    # AI conversation loop
    # ------------------------------------------------------------------ #

    async def _run_conversation(self, call_id: str) -> None:
        """Run the AI conversation loop for a call.

        This orchestrates:
        1. Play greeting
        2. Listen for caller speech (via audio streaming)
        3. STT → transcribe
        4. LLM → generate response
        5. TTS → synthesize audio
        6. Play response audio to caller
        7. Repeat until hangup

        The actual audio streaming is handled by FreeSWITCH's mod_audio_stream
        which connects to the orchestrator's WebSocket endpoint. This method
        handles the conversation logic.
        """
        try:
            session = await self.session_mgr.get_session(call_id)
            if not session:
                logger.error("call_handler.no_session", call_id=call_id)
                return

            tenant_id = session.tenant_id

            # Transition to ACTIVE
            await self.session_mgr.update_session(call_id, {
                "state": "active",
                "answered_at": datetime.utcnow().isoformat(),
            })

            # Publish call active event
            from orchestrator.models import EventType, SystemEvent
            self.event_bus.publish(SystemEvent(
                event_type=EventType.CALL_ACTIVE,
                call_id=call_id,
                tenant_id=tenant_id,
            ))

            # 1. Play greeting
            greeting = await self._get_greeting(tenant_id)
            greeting_audio = await self._synthesize_speech(greeting)
            if greeting_audio:
                await self._play_audio(call_id, greeting_audio)

            # 2. Start audio streaming to orchestrator WebSocket
            # This tells FreeSWITCH to stream audio bidirectionally
            ws_url = f"ws://{self.settings.orchestrator_host}:{self.settings.orchestrator_port}/api/v1/orchestrator/ws/call/{call_id}/audio"
            await self.esl.send_api(
                "uuid_broadcast",
                f"{call_id} exec::mod_audio_stream::{ws_url}"
            )

            # 3. Conversation loop runs via WebSocket audio exchange
            # The orchestrator gateway handles incoming audio chunks,
            # runs STT → LLM → TTS, and sends back audio responses.
            # This task stays alive to monitor the call and handle
            # any direct ESL commands needed.

            # Wait for the session to end
            while True:
                await asyncio.sleep(1.0)

                # Check if session is still active
                session = await self.session_mgr.get_session(call_id)
                if not session or session.state in ("ended", "archived"):
                    break

                # Check call duration limit
                if session.answered_at:
                    elapsed = (datetime.utcnow() - session.answered_at).total_seconds()
                    max_duration = self.settings.ai.max_call_duration_minutes * 60
                    if elapsed > max_duration:
                        logger.info("call_handler.max_duration_reached", call_id=call_id)
                        await self.esl.hangup(call_id, "normal_clearing")
                        break

        except asyncio.CancelledError:
            logger.info("call_handler.conversation_cancelled", call_id=call_id)
        except Exception as exc:
            logger.error("call_handler.conversation_error", call_id=call_id, error=str(exc))
        finally:
            self._call_tasks.pop(call_id, None)

    # ------------------------------------------------------------------ #
    # AI pipeline helpers
    # ------------------------------------------------------------------ #

    async def _get_greeting(self, tenant_id: str) -> str:
        """Get the greeting message for a tenant."""
        # Default greeting — in production this comes from tenant config
        recording_disclosure = ""
        if getattr(self.settings, 'recording_disclosure_enabled', True):
            recording_disclosure = " This call may be recorded for quality purposes."

        return f"Hello, thank you for calling.{recording_disclosure} How can I help you today?"

    async def _synthesize_speech(self, text: str) -> Optional[bytes]:
        """Synthesize speech using Piper TTS via the AI pipeline."""
        try:
            if self.ai_pipeline:
                audio = await self.ai_pipeline.tts.synthesize(text)
                return audio
            else:
                logger.warning("call_handler.no_tts_pipeline")
                return None
        except Exception as exc:
            logger.error("call_handler.tts_failed", error=str(exc))
            return None

    async def _play_audio(self, call_id: str, audio_data: bytes) -> None:
        """Play audio data to the caller via FreeSWITCH.

        Writes audio to a temp file and plays it back.
        For real-time streaming, the WebSocket audio path is preferred.
        """
        try:
            # Write to temp file
            file_path = f"/tmp/owlbell_{call_id}_{int(time.time())}.wav"
            import aiofiles
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(audio_data)

            # Play via FreeSWITCH
            await self.esl.playback(call_id, file_path)

        except Exception as exc:
            logger.error("call_handler.playback_failed", call_id=call_id, error=str(exc))

    async def _repeat_last_response(self, call_id: str) -> None:
        """Repeat the last AI response (DTMF 9)."""
        try:
            session = await self.session_mgr.get_session(call_id)
            if session and session.metadata.get("last_ai_response"):
                audio = await self._synthesize_speech(session.metadata["last_ai_response"])
                if audio:
                    await self._play_audio(call_id, audio)
        except Exception as exc:
            logger.error("call_handler.repeat_failed", call_id=call_id, error=str(exc))

    # ------------------------------------------------------------------ #
    # Transfer
    # ------------------------------------------------------------------ #

    async def _transfer_to_operator(self, call_id: str) -> None:
        """Transfer call to operator (DTMF 0)."""
        try:
            session = await self.session_mgr.get_session(call_id)
            if not session:
                return

            # Get transfer number from tenant config (fallback to env)
            transfer_number = getattr(self.settings, 'operator_transfer_number', None)
            if not transfer_number:
                logger.warning("call_handler.no_transfer_number", call_id=call_id)
                return

            logger.info("call_handler.transferring", call_id=call_id, to=transfer_number)

            await self.session_mgr.update_session(call_id, {
                "state": "holding",
                "transferred_to": transfer_number,
            })

            from orchestrator.models import EventType, SystemEvent
            self.event_bus.publish(SystemEvent(
                event_type=EventType.CALL_TRANSFERRED,
                call_id=call_id,
                tenant_id=session.tenant_id,
                payload={"transferred_to": transfer_number, "reason": "operator_request"},
            ))

            # Execute transfer via FreeSWITCH
            await self.esl.send_api(
                "uuid_transfer",
                f"{call_id} {transfer_number} XML default"
            )

        except Exception as exc:
            logger.error("call_handler.transfer_failed", call_id=call_id, error=str(exc))

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #

    async def _start_recording(self, call_id: str) -> None:
        """Start call recording (if enabled for tenant)."""
        try:
            file_path = f"{self.recording_dir}/{call_id}.wav"
            await self.esl.record(call_id, file_path, max_len=3600)
            logger.info("call_handler.recording_started", call_id=call_id, path=file_path)
        except Exception as exc:
            logger.error("call_handler.recording_failed", call_id=call_id, error=str(exc))

    # ------------------------------------------------------------------ #
    # Cleanup
    # ------------------------------------------------------------------ #

    async def _cleanup_call(self, call_id: str, reason: str) -> None:
        """Clean up a call: cancel tasks, update session, publish events."""
        # Cancel conversation task
        task = self._call_tasks.pop(call_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Update session to ENDED
        try:
            session = await self.session_mgr.get_session(call_id)
            if session:
                await self.session_mgr.update_session(call_id, {
                    "state": "ended",
                    "ended_at": datetime.utcnow().isoformat(),
                    "end_reason": reason,
                })

                # Publish call ended event
                from orchestrator.models import EventType, SystemEvent
                duration = 0
                if hasattr(session, 'answered_at') and session.answered_at:
                    duration = (datetime.utcnow() - session.answered_at).total_seconds()

                self.event_bus.publish(SystemEvent(
                    event_type=EventType.CALL_ENDED,
                    call_id=call_id,
                    tenant_id=session.tenant_id,
                    payload={
                        "duration_seconds": duration,
                        "end_reason": reason,
                        "caller_number": session.caller_number,
                    },
                ))

                logger.info(
                    "call_handler.call_ended",
                    call_id=call_id,
                    duration=duration,
                    reason=reason,
                )

        except Exception as exc:
            logger.error("call_handler.cleanup_failed", call_id=call_id, error=str(exc))

    # ------------------------------------------------------------------ #
    # Tenant resolution
    # ------------------------------------------------------------------ #

    async def _resolve_tenant(self, destination_number: str) -> str:
        """Resolve tenant ID from destination phone number by querying the database."""
        session_maker = get_session_maker()
        if session_maker is None:
            logger.warning("call_handler.no_session_maker", destination=destination_number)
            return str(uuid.UUID(int=1))

        from sqlalchemy import select
        from backend.db.models.tenant import Tenant

        async with session_maker() as session:
            try:
                result = await session.execute(
                    select(Tenant).where(Tenant.business_phone == destination_number)
                )
                tenant = result.scalar_one_or_none()
                if tenant is None:
                    logger.warning("call_handler.tenant_not_found", destination=destination_number)
                    return str(uuid.UUID(int=1))
                logger.info("call_handler.tenant_resolved", tenant_id=str(tenant.id), destination=destination_number)
                return str(tenant.id)
            except Exception as exc:
                logger.error("call_handler.tenant_resolution_error", destination=destination_number, error=str(exc))
                return str(uuid.UUID(int=1))
