"""api/routes/retell_webhooks.py - Webhook receiver for Retell AI call events.

Endpoints (mounted at /api/v1/webhooks/retell by api/main.py):
    POST /  -> receive Retell call_started / call_ended / call_analyzed events

Retell sends webhooks for call lifecycle events. This handler:
    - Verifies the Retell signature (X-Retell-Signature header)
    - Creates/updates Call records in the database
    - Logs transcripts, cost, and analysis data
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncGenerator, Optional
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from backend.db.models.ai import Conversation, Transcript
from backend.db.models.call import Call, CallLeg
from backend.db.models.enums import (
    AIModel,
    CallDirection,
    CallResult,
    CallStatus,
    TranscriptSource,
)
from backend.integrations.retell.service import verify_webhook

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhooks/retell", tags=["Webhooks"])


def _parse_timestamp(ts: Optional[int]) -> Optional[datetime]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).replace(tzinfo=None)


@asynccontextmanager
async def _get_session() -> AsyncGenerator[Any, None]:
    """Get a DB session with proper cleanup (replaces async for...break)."""
    from backend.dependencies import get_session_maker

    sm = get_session_maker()
    if sm is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database not initialized")
    session = sm()
    try:
        yield session
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@router.post("", status_code=status.HTTP_200_OK)
async def handle_retell_webhook(request: Request) -> dict[str, Any]:
    """Receive a Retell webhook event.

    Expected payload:
        {
            "event": "call_started" | "call_ended" | "call_analyzed",
            "call_id": "abc123...",
            "phone_number": "+14155551234",
            "agent_id": "agent_...",
            "caller_number": "+12125551234",
            "direction": "inbound" | "outbound",
            ...
        }
    """
    body = await request.body()
    signature = request.headers.get("X-Retell-Signature", "")

    if not verify_webhook(body, signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")

    payload = await request.json()
    event = payload.get("event")
    call_id = payload.get("call_id")

    logger.info("retell.webhook_received", retell_event=event, call_id=call_id)

    if event == "call_started":
        await _handle_call_started(payload)
    elif event == "call_ended":
        await _handle_call_ended(payload)
    elif event == "call_analyzed":
        await _handle_call_analyzed(payload)
    else:
        logger.warning("retell.webhook_unknown_event", retell_event=event)

    return {"success": True}


async def _handle_call_started(payload: dict[str, Any]) -> None:
    call_id = payload.get("call_id")
    phone_number = payload.get("phone_number", "")
    caller_number = payload.get("caller_number", "")
    direction = payload.get("direction", "inbound")
    agent_id = payload.get("agent_id", "")
    start_timestamp = payload.get("start_timestamp")

    from backend.db.models.tenant import Tenant

    async with _get_session() as db:
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.business_phone == phone_number)
        )
        tenant = tenant_result.scalar_one_or_none()

        if not tenant:
            logger.warning("retell.call_no_tenant", phone_number=phone_number, call_id=call_id)
            return

        call = Call(
            id=uuid4(),
            tenant_id=tenant.id,
            call_sid=call_id,
            direction=CallDirection.INBOUND if direction == "inbound" else CallDirection.OUTBOUND,
            caller_number=caller_number,
            destination_number=phone_number,
            status=CallStatus.ACTIVE,
            ai_handled=True,
            ai_model_used=AIModel.RETELL_AI,
            started_at=_parse_timestamp(start_timestamp) or datetime.utcnow(),
            metadata_json={"retell_call_id": call_id, "retell_agent_id": agent_id},
        )
        db.add(call)

        leg = CallLeg(
            id=uuid4(),
            call_id=call.id,
            tenant_id=tenant.id,
            leg_type="caller",
            leg_index=1,
            phone_number=caller_number,
        )
        db.add(leg)

    logger.info("retell.call_recorded", call_id=call_id, tenant_id=str(tenant.id))


async def _handle_call_ended(payload: dict[str, Any]) -> None:
    call_id = payload.get("call_id")
    end_timestamp = payload.get("end_timestamp")
    duration_ms = payload.get("duration_ms")
    call_result = payload.get("call_result", "completed")

    async with _get_session() as db:
        result = await db.execute(
            select(Call).where(
                Call.metadata_json["retell_call_id"].as_string() == call_id
            )
        )
        call = result.scalar_one_or_none()

        if not call:
            logger.warning("retell.call_not_found", call_id=call_id)
            return

        call.status = CallStatus.COMPLETED
        call.ended_at = _parse_timestamp(end_timestamp) or datetime.utcnow()
        if duration_ms:
            call.duration_seconds = duration_ms // 1000

        result_map = {
            "completed": CallResult.SUCCESS,
            "voicemail": CallResult.VOICEMAIL_LEFT,
            "failed": CallResult.FAILED,
            "busy": CallResult.BUSY,
            "no_answer": CallResult.NO_ANSWER,
            "transferred": CallResult.TRANSFERRED,
        }
        call.result = result_map.get(call_result, CallResult.SUCCESS)

    logger.info("retell.call_ended", call_id=call_id)


async def _handle_call_analyzed(payload: dict[str, Any]) -> None:
    call_id = payload.get("call_id")
    transcript = payload.get("transcript")
    summary = payload.get("summary", {})

    async with _get_session() as db:
        result = await db.execute(
            select(Call).where(
                Call.metadata_json["retell_call_id"].as_string() == call_id
            )
        )
        call = result.scalar_one_or_none()

        if not call:
            logger.warning("retell.call_not_found_analyzed", call_id=call_id)
            return

        call.transcript_summary = summary.get("summary") if isinstance(summary, dict) else str(summary)

        sentiment = summary.get("sentiment_score") if isinstance(summary, dict) else None
        if sentiment is not None:
            call.sentiment_score = Decimal(str(sentiment))

        intent = summary.get("intent_detected") if isinstance(summary, dict) else None
        if intent:
            call.intent_detected = intent

        cost_cents = payload.get("cost_cents")
        if cost_cents is not None:
            call.estimated_cost = Decimal(str(cost_cents / 100))

        call.talk_time_seconds = payload.get("talk_time_ms", 0) // 1000

        conversation_text = (
            transcript if isinstance(transcript, str)
            else "\n".join(
                f"{m.get('role', 'unknown')}: {m.get('content', '')}"
                for m in (transcript if isinstance(transcript, list) else [])
            )
        )

        conv = Conversation(
            id=uuid4(),
            call_id=call.id,
            tenant_id=call.tenant_id,
            turn_count=len(transcript) if isinstance(transcript, list) else 0,
            summary=call.transcript_summary,
        )
        db.add(conv)

        transcript_entry = Transcript(
            id=uuid4(),
            call_id=call.id,
            tenant_id=call.tenant_id,
            text=conversation_text,
            segment_start=0,
            segment_end=1,
            source=TranscriptSource.RETELL_AI,
            speaker="system",
        )
        db.add(transcript_entry)

    logger.info("retell.call_analyzed", call_id=call_id)


# ---------------------------------------------------------------------------
# Test endpoint — creates a Retell web call and returns the access token
# ---------------------------------------------------------------------------


@router.post("/test-token")
async def create_test_web_call(payload: dict):
    """Create a Retell web call for testing and return the access token."""
    from retell import Retell
    from backend.config import get_settings
    settings = get_settings()
    key = settings.integrations.retell_api_key
    if not key:
        return JSONResponse(status_code=400, content={"error": "Retell not configured"})

    client = Retell(api_key=key.get_secret_value())
    agent_id = payload.get("agent_id")
    dynamic_vars = payload.get("dynamic_variables", {})

    if not agent_id:
        return JSONResponse(status_code=400, content={"error": "agent_id required"})

    try:
        result = client.call.create_web_call(
            agent_id=agent_id,
            retell_llm_dynamic_variables=dynamic_vars,
        )
        return {
            "call_id": result.call_id,
            "access_token": result.access_token,
        }
    except Exception as exc:
        logger.error("retell.test_token_failed", error=str(exc))
        return JSONResponse(status_code=500, content={"error": str(exc)})
