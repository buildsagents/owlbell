"""api/routes/calls.py - Call management route handlers (10 endpoints).

Provides call listing, detail retrieval, transcripts, recordings,
transfer control, and live call monitoring.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant, CurrentUser, get_current_tenant, get_db_session
from api.schemas.base import (
    CallDirection,
    CallEndReason,
    CallStatus,
    ResponseMeta,
    SuccessResponse,
)
from api.schemas.calls import (
    CallListParams,
    CallListResponse,
    CallMetrics,
    CallRecord,
    CallRecordingRequest,
    CallSummaryResponse,
    CallTagRequest,
    CallTransferRequest,
    CallTransferResponse,
    CallUpdateRequest,
    CallerInfo,
    LiveCall,
    LiveCallsResponse,
    TranscriptEntry,
    TranscriptResponse,
)
from backend.db.models.call import Call, Recording
from backend.db.models.ai import Transcript

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/calls", tags=["Calls"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DB_TO_API_STATUS = {
    "queued": CallStatus.RINGING,
    "ringing": CallStatus.RINGING,
    "answered": CallStatus.CONNECTED,
    "active": CallStatus.CONNECTED,
    "on_hold": CallStatus.ON_HOLD,
    "transferred": CallStatus.CONNECTED,
    "completed": CallStatus.ENDED,
    "failed": CallStatus.ENDED,
    "voicemail": CallStatus.ENDED,
    "no_answer": CallStatus.ENDED,
}

_DB_TO_API_END_REASON = {
    "success": CallEndReason.HANGUP_BY_CALLER,
    "hangup": CallEndReason.HANGUP_BY_CALLER,
    "voicemail_left": CallEndReason.HANGUP_BY_CALLER,
    "transferred": CallEndReason.TRANSFERRED,
    "no_answer": CallEndReason.NO_ANSWER,
    "busy": CallEndReason.BUSY,
    "failed": CallEndReason.ERROR,
    "error": CallEndReason.ERROR,
}

_LIVE_STATUSES = {"queued", "ringing", "answered", "active", "on_hold"}


def _map_status(db_status: str) -> CallStatus:
    return _DB_TO_API_STATUS.get(db_status, CallStatus.ENDED)


def _map_end_reason(db_result: str | None) -> CallEndReason | None:
    if db_result is None:
        return None
    return _DB_TO_API_END_REASON.get(db_result)


def _call_to_record(call: Call, transcripts: list[Transcript] | None = None, recordings: list[Recording] | None = None) -> CallRecord:
    transcript_id = transcripts[0].id if transcripts else None
    recording_url = recordings[0].access_url if recordings and recordings[0].access_url else None

    return CallRecord(
        id=call.id,
        tenant_id=call.tenant_id,
        status=_map_status(call.status.value if hasattr(call.status, "value") else str(call.status)),
        direction=CallDirection(call.direction.value if hasattr(call.direction, "value") else str(call.direction)),
        caller=CallerInfo(
            phone_number=call.caller_number,
            name=call.caller_name,
        ),
        start_time=call.started_at,
        end_time=call.ended_at,
        end_reason=_map_end_reason(call.result.value if call.result and hasattr(call.result, "value") else (str(call.result) if call.result else None)),
        transcript_id=transcript_id,
        recording_url=recording_url,
        metrics=CallMetrics(
            duration_seconds=call.duration_seconds or 0,
            sentiment_score=float(call.sentiment_score) if call.sentiment_score is not None else None,
        ),
        handled_by_ai=call.ai_handled,
        transferred_to=call.transferred_to,
        tags=call.tags or [],
        created_at=call.created_at,
        updated_at=call.updated_at,
    )


def _build_transcript_response(
    call_id: uuid.UUID,
    tenant_id: uuid.UUID,
    transcripts: list[Transcript],
    call_created_at: datetime,
) -> TranscriptResponse:
    entries = []
    for i, t in enumerate(transcripts):
        speaker = "ai" if t.speaker == "agent" else t.speaker
        entries.append(
            TranscriptEntry(
                sequence=i,
                speaker=speaker,
                text=t.text,
                timestamp=t.created_at,
                confidence=float(t.confidence) if t.confidence is not None else None,
                latency_ms=None,
            )
        )

    transcript_id = transcripts[0].id if transcripts else uuid.uuid4()

    return TranscriptResponse(
        id=transcript_id,
        call_id=call_id,
        tenant_id=tenant_id,
        entries=entries,
        created_at=call_created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=SuccessResponse[CallListResponse],
    summary="List calls",
    description="List calls with pagination and filtering.",
)
async def list_calls(
    params: CallListParams = Depends(),
    tenant: Any = CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[CallListResponse]:
    tenant_id = tenant.id
    query = select(Call).where(Call.tenant_id == tenant_id)

    if params.status:
        db_status_map = {
            CallStatus.RINGING: ["queued", "ringing"],
            CallStatus.CONNECTED: ["answered", "active", "transferred"],
            CallStatus.ON_HOLD: ["on_hold"],
            CallStatus.ENDED: ["completed", "failed", "voicemail", "no_answer"],
        }
        allowed = db_status_map.get(params.status, [])
        if allowed:
            query = query.where(Call.status.in_(allowed))

    if params.direction:
        query = query.where(Call.direction == params.direction.value)

    if params.caller_number:
        query = query.where(Call.caller_number.ilike(f"%{params.caller_number}%"))

    if params.handled_by_ai is not None:
        query = query.where(Call.ai_handled == params.handled_by_ai)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    offset = (params.page - 1) * params.per_page
    query = query.order_by(Call.started_at.desc()).limit(params.per_page).offset(offset)
    result = await db.execute(query)
    calls = result.scalars().all()

    records = [_call_to_record(c) for c in calls]

    return SuccessResponse(
        data=CallListResponse(items=records, total=total),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/live",
    response_model=SuccessResponse[LiveCallsResponse],
    summary="Active calls",
    description="Get currently active (live) calls.",
)
async def get_live_calls(
    tenant: Any = CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[LiveCallsResponse]:
    tenant_id = tenant.id
    result = await db.execute(
        select(Call)
        .where(Call.tenant_id == tenant_id)
        .where(Call.status.in_(_LIVE_STATUSES))
        .order_by(Call.started_at.desc())
    )
    calls = result.scalars().all()

    live_calls = []
    for c in calls:
        db_status = c.status.value if hasattr(c.status, "value") else str(c.status)
        duration = c.duration_seconds or 0

        snippet = None
        if c.transcript_summary:
            snippet = c.transcript_summary[:100]

        live_calls.append(
            LiveCall(
                call_id=c.id,
                caller_number=c.caller_number,
                caller_name=c.caller_name,
                status=_map_status(db_status),
                start_time=c.started_at,
                duration_seconds=duration,
                ai_response_count=c.llm_tokens_used,
                current_transcript_snippet=snippet,
                sentiment=float(c.sentiment_score) if c.sentiment_score is not None else None,
            )
        )

    return SuccessResponse(
        data=LiveCallsResponse(calls=live_calls, count=len(live_calls)),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/summary",
    response_model=SuccessResponse[CallSummaryResponse],
    summary="Call summary",
    description="Get aggregated call statistics for a date range.",
)
async def get_call_summary(
    start_date: datetime,
    end_date: datetime,
    tenant: Any = CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[CallSummaryResponse]:
    tenant_id = tenant.id
    base = select(Call).where(
        Call.tenant_id == tenant_id,
        Call.started_at >= start_date,
        Call.started_at <= end_date,
    )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    total_duration = (await db.execute(
        select(func.coalesce(func.sum(Call.duration_seconds), 0)).select_from(base.subquery())
    )).scalar() or 0
    ai_handled = (await db.execute(
        select(func.count()).select_from(base.where(Call.ai_handled == True).subquery())
    )).scalar() or 0
    transferred = (await db.execute(
        select(func.count()).select_from(base.where(Call.transferred_to.isnot(None)).subquery())
    )).scalar() or 0
    missed = (await db.execute(
        select(func.count()).select_from(base.where(Call.status == "no_answer").subquery())
    )).scalar() or 0

    return SuccessResponse(
        data=CallSummaryResponse(
            total_calls=total,
            total_duration_seconds=total_duration,
            avg_duration_seconds=total_duration / max(total, 1),
            ai_handled_count=ai_handled,
            transferred_count=transferred,
            missed_count=missed,
            period_start=start_date,
            period_end=end_date,
        ),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/{call_id}",
    response_model=SuccessResponse[CallRecord],
    summary="Get call detail",
    description="Get detailed information about a specific call.",
)
async def get_call(
    call_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[CallRecord]:
    result = await db.execute(
        select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return SuccessResponse(data=_call_to_record(call), meta=ResponseMeta(request_id=""))


@router.patch(
    "/{call_id}",
    response_model=SuccessResponse[CallRecord],
    summary="Update call",
    description="Update call tags and notes.",
)
async def update_call(
    call_id: uuid.UUID,
    body: CallUpdateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[CallRecord]:
    result = await db.execute(
        select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    if body.tags is not None:
        call.tags = body.tags
    if body.notes is not None:
        call.metadata_json = {**(call.metadata_json or {}), "notes": body.notes}
    call.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(call)

    return SuccessResponse(data=_call_to_record(call), meta=ResponseMeta(request_id=""))


@router.post(
    "/{call_id}/transfer",
    response_model=SuccessResponse[CallTransferResponse],
    summary="Transfer call",
    description="Transfer an active call to a destination.",
)
async def transfer_call(
    call_id: uuid.UUID,
    body: CallTransferRequest,
    tenant: Any = CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[CallTransferResponse]:
    result = await db.execute(
        select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    from backend.db.models.enums import CallStatus as DBCallStatus
    call.status = DBCallStatus.ON_HOLD
    call.transferred_to = body.destination
    call.updated_at = datetime.utcnow()

    await db.flush()

    return SuccessResponse(
        data=CallTransferResponse(
            call_id=call_id,
            status="transferring",
            destination=body.destination,
            message=f"Call transferring to {body.destination}",
        ),
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/{call_id}/tags",
    response_model=SuccessResponse[CallRecord],
    summary="Add tags",
    description="Add tags to a call.",
)
async def add_call_tags(
    call_id: uuid.UUID,
    body: CallTagRequest,
    tenant: Any = CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[CallRecord]:
    result = await db.execute(
        select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    existing = set(call.tags or [])
    existing.update(body.tags)
    call.tags = list(existing)
    call.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(call)

    return SuccessResponse(data=_call_to_record(call), meta=ResponseMeta(request_id=""))


@router.delete(
    "/{call_id}/tags/{tag}",
    response_model=SuccessResponse[CallRecord],
    summary="Remove tag",
    description="Remove a tag from a call.",
)
async def remove_call_tag(
    call_id: uuid.UUID,
    tag: str,
    tenant: Any = CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[CallRecord]:
    result = await db.execute(
        select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    call.tags = [t for t in (call.tags or []) if t != tag]
    call.updated_at = datetime.utcnow()

    await db.flush()
    await db.refresh(call)

    return SuccessResponse(data=_call_to_record(call), meta=ResponseMeta(request_id=""))


@router.get(
    "/{call_id}/transcript",
    response_model=SuccessResponse[TranscriptResponse],
    summary="Get transcript",
    description="Get the transcript for a call.",
)
async def get_transcript(
    call_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[TranscriptResponse]:
    call_result = await db.execute(
        select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id)
    )
    call = call_result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    transcript_result = await db.execute(
        select(Transcript)
        .where(Transcript.call_id == call_id, Transcript.tenant_id == tenant.id)
        .order_by(Transcript.segment_start)
    )
    transcripts = list(transcript_result.scalars().all())

    response = _build_transcript_response(
        call_id=call_id,
        tenant_id=tenant.id,
        transcripts=transcripts,
        call_created_at=call.created_at,
    )

    return SuccessResponse(data=response, meta=ResponseMeta(request_id=""))


@router.get(
    "/{call_id}/recording",
    response_model=SuccessResponse[dict],
    summary="Get recording URL",
    description="Get the signed URL for a call recording.",
)
async def get_recording_url(
    call_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[dict]:
    call_result = await db.execute(
        select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id)
    )
    call = call_result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    rec_result = await db.execute(
        select(Recording)
        .where(Recording.call_id == call_id, Recording.tenant_id == tenant.id)
        .order_by(Recording.created_at)
        .limit(1)
    )
    recording = rec_result.scalar_one_or_none()
    if not recording or not recording.access_url:
        raise HTTPException(status_code=404, detail="Recording not found")

    return SuccessResponse(
        data={
            "recording_url": recording.access_url,
            "expires_at": (recording.access_expires_at or (datetime.utcnow() + timedelta(hours=1))).isoformat(),
        },
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/{call_id}/recording",
    response_model=SuccessResponse[dict],
    summary="Control recording",
    description="Start, stop, pause, or resume call recording.",
)
async def control_recording(
    call_id: uuid.UUID,
    body: CallRecordingRequest,
    tenant: Any = CurrentTenant,
    db: AsyncSession = Depends(get_db_session),
) -> SuccessResponse[dict]:
    result = await db.execute(
        select(Call).where(Call.id == call_id, Call.tenant_id == tenant.id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return SuccessResponse(
        data={
            "call_id": str(call_id),
            "action": body.action,
            "status": f"recording_{body.action}ed",
        },
        meta=ResponseMeta(request_id=""),
    )
