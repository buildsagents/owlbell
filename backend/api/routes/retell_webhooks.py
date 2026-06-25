"""api/routes/retell_webhooks.py - Webhook receiver for Retell AI call events.

Endpoints (mounted at /api/v1/webhooks/retell by api/main.py):
    POST /  -> receive Retell call_started / call_ended / call_analyzed events

Retell sends webhooks for call lifecycle events. This handler:
    - Verifies the Retell signature (X-Retell-Signature header)
    - Creates/updates Call records in the database
    - Logs transcripts, cost, and analysis data
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from api.dependencies import get_db_session
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
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)


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

    logger.info("retell.webhook_received", event=event, call_id=call_id)

    if event == "call_started":
        await _handle_call_started(payload)
    elif event == "call_ended":
        await _handle_call_ended(payload)
    elif event == "call_analyzed":
        await _handle_call_analyzed(payload)
    else:
        logger.warning("retell.webhook_unknown_event", event=event)

    return {"success": True}


async def _get_call_by_retell_id(retell_call_id: str) -> Optional[Call]:
    async for db in get_db_session():
        break
    result = await db.execute(
        select(Call).where(Call.metadata_json["retell_call_id"].as_string() == retell_call_id)
    )
    return result.scalar_one_or_none()


async def _handle_call_started(payload: dict[str, Any]) -> None:
    call_id = payload.get("call_id")
    phone_number = payload.get("phone_number", "")
    caller_number = payload.get("caller_number", "")
    direction = payload.get("direction", "inbound")
    agent_id = payload.get("agent_id", "")
    start_timestamp = payload.get("start_timestamp")

    # Look up which tenant owns this phone number
    async for db in get_db_session():
        break

    from backend.db.models.tenant import TenantConfig

    config_result = await db.execute(
        select(TenantConfig).where(
            TenantConfig.key == "assigned_phone",
            TenantConfig.value == phone_number,
        )
    )
    config = config_result.scalar_one_or_none()
    tenant_id = config.tenant_id if config else None

    if not tenant_id:
        logger.warning("retell.call_no_tenant", phone_number=phone_number, call_id=call_id)
        return

    call = Call(
        id=uuid4(),
        tenant_id=tenant_id,
        call_sid=call_id,
        direction=CallDirection.INBOUND if direction == "inbound" else CallDirection.OUTBOUND,
        caller_number=caller_number,
        destination_number=phone_number,
        status=CallStatus.IN_PROGRESS,
        ai_handled=True,
        ai_model_used=AIModel.RETELL_AI,
        started_at=_parse_timestamp(start_timestamp) or datetime.now(timezone.utc),
        metadata_json={"retell_call_id": call_id, "retell_agent_id": agent_id},
    )
    db.add(call)

    leg = CallLeg(
        id=uuid4(),
        call_id=call.id,
        tenant_id=tenant_id,
        leg_type="caller",
        leg_index=1,
        phone_number=caller_number,
    )
    db.add(leg)

    await db.commit()
    logger.info("retell.call_recorded", call_id=call_id, tenant_id=str(tenant_id))


async def _handle_call_ended(payload: dict[str, Any]) -> None:
    call_id = payload.get("call_id")
    end_timestamp = payload.get("end_timestamp")
    duration_ms = payload.get("duration_ms")
    call_result = payload.get("call_result", "completed")

    call = await _get_call_by_retell_id(call_id)
    if not call:
        logger.warning("retell.call_not_found", call_id=call_id)
        return

    call.status = CallStatus.COMPLETED
    call.ended_at = _parse_timestamp(end_timestamp) or datetime.now(timezone.utc)
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

    async for db in get_db_session():
        break
    db.add(call)
    await db.commit()
    logger.info("retell.call_ended", call_id=call_id)


async def _handle_call_analyzed(payload: dict[str, Any]) -> None:
    call_id = payload.get("call_id")
    transcript = payload.get("transcript")
    summary = payload.get("summary", {})

    call = await _get_call_by_retell_id(call_id)
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

    async for db in get_db_session():
        break

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
        content=conversation_text,
        source=TranscriptSource.RETELL_AI,
        speaker="system",
    )
    db.add(transcript_entry)

    db.add(call)
    await db.commit()
    logger.info("retell.call_analyzed", call_id=call_id)
