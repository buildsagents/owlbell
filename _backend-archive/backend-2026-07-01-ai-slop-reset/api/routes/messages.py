"""api/routes/messages.py - Message management route handlers (8 endpoints).

Provides message listing, detail, creation, update, read marking,
forwarding, resolution, and deletion. Backed by the Call model
(voicemail_left=True) via MessageService.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant, CurrentUser, DBSession, get_db_session
from api.schemas.base import (
    AppointmentStatus,
    MessageChannel,
    MessagePriority,
    ResponseMeta,
    SuccessResponse,
)
from api.schemas.messages import (
    MessageContactInfo,
    MessageCreateRequest,
    MessageForwardRequest,
    MessageListParams,
    MessageListResponse,
    MessageReadRequest,
    MessageRecord,
    MessageResolveRequest,
    MessageStatsResponse,
    MessageUpdateRequest,
)
from backend.business.messages.service import MessageService
from backend.db.models.call import Call
from backend.db.models.enums import CallStatus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/messages", tags=["Messages"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _call_to_message_record(call: Call) -> MessageRecord:
    """Convert a Call (voicemail) ORM row to the MessageRecord schema."""
    meta = call.metadata_json or {}

    contact = MessageContactInfo(
        name=call.caller_name,
        phone=call.caller_number,
        email=meta.get("contact_email"),
        company=meta.get("company"),
        best_time_to_call=meta.get("best_time_to_call"),
    )

    read_by_data = meta.get("read_by", [])
    read_by_user = None
    read_at_time = None
    if isinstance(read_by_data, list) and read_by_data:
        last_read = read_by_data[-1]
        read_by_user = uuid.UUID(last_read["user_id"]) if isinstance(last_read, dict) else None
        if isinstance(last_read, dict) and last_read.get("read_at"):
            try:
                read_at_time = datetime.fromisoformat(last_read["read_at"])
            except (ValueError, TypeError):
                read_at_time = None
    elif isinstance(read_by_data, str):
        try:
            read_by_user = uuid.UUID(read_by_data)
        except (ValueError, AttributeError):
            pass

    forwards = meta.get("forwards", [])
    forwarded_to = []
    if isinstance(forwards, list):
        for f in forwards:
            if isinstance(f, dict) and f.get("destination"):
                forwarded_to.append(f["destination"])

    is_resolved = meta.get("resolved", False)
    tags = list(call.tags or [])
    if is_resolved and "resolved" not in tags:
        tags.append("resolved")

    channel_str = meta.get("channel", "voice")
    try:
        channel = MessageChannel(channel_str)
    except ValueError:
        channel = MessageChannel.VOICE

    priority_str = meta.get("priority", "normal")
    try:
        priority = MessagePriority(priority_str)
    except ValueError:
        priority = MessagePriority.NORMAL

    return MessageRecord(
        id=call.id,
        tenant_id=call.tenant_id,
        call_id=call.id,
        channel=channel,
        priority=priority,
        contact=contact,
        subject=meta.get("subject", meta.get("ai_summary")),
        body=call.transcript_summary or call.caller_number or "",
        ai_summary=meta.get("ai_summary"),
        is_read=len(read_by_data) > 0 if isinstance(read_by_data, list) else bool(read_by_data),
        read_by=read_by_user,
        read_at=read_at_time,
        forwarded_to=forwarded_to,
        tags=tags,
        created_at=call.started_at,
        updated_at=call.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=SuccessResponse[MessageListResponse],
    summary="List messages",
    description="List messages with pagination, filtering, and search.",
)
async def list_messages(
    params: MessageListParams = Depends(),
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[MessageListResponse]:
    """List messages with filters."""
    svc = MessageService(db, tenant.id)

    filters: dict[str, Any] = {}
    if params.is_read is not None:
        filters["is_read"] = params.is_read
    if params.priority:
        filters["priority"] = params.priority.value
    if params.channel:
        filters["channel"] = params.channel.value
    if params.search:
        filters["search"] = params.search
    if params.start_date:
        filters["date_from"] = params.start_date
    if params.end_date:
        filters["date_to"] = params.end_date

    items, total = await svc.list_messages(
        filters=filters or None,
        limit=params.per_page,
        offset=(params.page - 1) * params.per_page,
    )

    records = [_call_to_message_record(c) for c in items]

    unread = sum(1 for r in records if not r.is_read)

    return SuccessResponse(
        data=MessageListResponse(items=records, total=total, unread_count=unread),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/stats",
    response_model=SuccessResponse[MessageStatsResponse],
    summary="Message statistics",
    description="Get aggregated message statistics.",
)
async def get_message_stats(
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[MessageStatsResponse]:
    """Get message statistics."""
    svc = MessageService(db, tenant.id)
    stats = await svc.get_message_stats()

    total = 0
    for row in stats:
        if "total" in row:
            total = row["total"]

    unread_result = await db.execute(
        select(func.count()).select_from(Call).where(
            Call.tenant_id == tenant.id,
            Call.voicemail_left == True,
        )
    )
    total_all = unread_result.scalar_one()

    # Derive by_priority / by_channel from metadata
    channel_expr = Call.metadata_json["channel"].as_string()
    channel_query = await db.execute(
        select(channel_expr.label("channel"), func.count().label("count"))
        .where(
            Call.tenant_id == tenant.id,
            Call.voicemail_left == True,
            Call.metadata_json["channel"].isnot(None),
        )
        .group_by(channel_expr)
    )
    by_channel: dict[str, int] = {}
    for row in channel_query:
        by_channel[str(row[0])] = row[1]

    if not by_channel:
        by_channel = {"voice": total_all}

    priority_expr = Call.metadata_json["priority"].as_string()
    priority_query = await db.execute(
        select(priority_expr.label("priority"), func.count().label("count"))
        .where(
            Call.tenant_id == tenant.id,
            Call.voicemail_left == True,
            Call.metadata_json["priority"].isnot(None),
        )
        .group_by(priority_expr)
    )
    by_priority: dict[str, int] = {}
    for row in priority_query:
        by_priority[str(row[0])] = row[1]

    if not by_priority:
        by_priority = {"normal": total_all}

    unread_count_result = await db.execute(
        select(func.count()).select_from(Call).where(
            Call.tenant_id == tenant.id,
            Call.voicemail_left == True,
            Call.metadata_json["read_by"].is_(None),
        )
    )
    unread = unread_count_result.scalar_one()

    now = datetime.utcnow()
    period_start = now - timedelta(days=30)

    return SuccessResponse(
        data=MessageStatsResponse(
            total_messages=total_all,
            unread_count=unread,
            by_priority=by_priority,
            by_channel=by_channel,
            period_start=period_start,
            period_end=now,
        ),
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "",
    response_model=SuccessResponse[MessageRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create message",
    description="Create a new message manually.",
)
async def create_message(
    body: MessageCreateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[MessageRecord]:
    """Create a new message (recorded as a voicemail Call)."""
    svc = MessageService(db, tenant.id)

    metadata: dict[str, Any] = {
        "channel": body.channel.value,
        "priority": body.priority.value,
        "subject": body.subject,
        "ai_summary": None,
        "read_by": [],
        "forwards": [],
    }
    if body.contact.name:
        metadata["contact_email"] = body.contact.email
    if body.contact.company:
        metadata["company"] = body.contact.company
    if body.contact.best_time_to_call:
        metadata["best_time_to_call"] = body.contact.best_time_to_call

    data: dict[str, Any] = {
        "caller_name": body.contact.name,
        "caller_number": body.contact.phone or "",
        "call_sid": str(uuid.uuid4()),
        "direction": "inbound",
        "destination_number": "",
        "status": CallStatus.VOICEMAIL,
        "voicemail_left": True,
        "transcript_summary": body.body,
        "tags": body.tags,
        "metadata_json": metadata,
    }

    call = await svc.create_message(data)
    await db.refresh(call)

    return SuccessResponse(
        data=_call_to_message_record(call),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/{message_id}",
    response_model=SuccessResponse[MessageRecord],
    summary="Get message",
    description="Get a single message by ID.",
)
async def get_message(
    message_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[MessageRecord]:
    """Get message detail."""
    svc = MessageService(db, tenant.id)
    try:
        call = await svc.get_message(message_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Message not found")

    return SuccessResponse(
        data=_call_to_message_record(call),
        meta=ResponseMeta(request_id=""),
    )


@router.patch(
    "/{message_id}",
    response_model=SuccessResponse[MessageRecord],
    summary="Update message",
    description="Update message fields.",
)
async def update_message(
    message_id: uuid.UUID,
    body: MessageUpdateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[MessageRecord]:
    """Update message fields."""
    svc = MessageService(db, tenant.id)
    try:
        call = await svc.get_message(message_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Message not found")

    meta = dict(call.metadata_json or {})

    update_data: dict[str, Any] = {}
    if body.priority is not None:
        meta["priority"] = body.priority.value
    if body.subject is not None:
        meta["subject"] = body.subject
    if body.body is not None:
        update_data["transcript_summary"] = body.body
    if body.tags is not None:
        update_data["tags"] = body.tags

    update_data["metadata_json"] = meta

    call = await svc.update_message(message_id, update_data)
    await db.refresh(call)

    return SuccessResponse(
        data=_call_to_message_record(call),
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/{message_id}/read",
    response_model=SuccessResponse[MessageRecord],
    summary="Mark read/unread",
    description="Mark message as read or unread.",
)
async def mark_message_read(
    message_id: uuid.UUID,
    body: MessageReadRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[MessageRecord]:
    """Mark message as read or unread."""
    svc = MessageService(db, tenant.id)
    try:
        call = await svc.get_message(message_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Message not found")

    meta = dict(call.metadata_json or {})
    if body.is_read:
        read_by = meta.get("read_by", [])
        if not isinstance(read_by, list):
            read_by = []
        read_by.append({
            "user_id": str(user.id),
            "read_at": datetime.utcnow().isoformat(),
        })
        meta["read_by"] = read_by
        meta["read_count"] = len(read_by)
    else:
        meta["read_by"] = []
        meta["read_count"] = 0

    call.metadata_json = meta
    await db.flush()
    await db.refresh(call)

    return SuccessResponse(
        data=_call_to_message_record(call),
        meta=ResponseMeta(request_id=""),
    )


@router.patch(
    "/{message_id}/resolve",
    response_model=SuccessResponse[MessageRecord],
    summary="Resolve message",
    description="Mark message as resolved with optional note.",
)
async def resolve_message(
    message_id: uuid.UUID,
    body: MessageResolveRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[MessageRecord]:
    """Mark message as resolved."""
    svc = MessageService(db, tenant.id)
    try:
        call = await svc.get_message(message_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Message not found")

    call = await svc.resolve_message(message_id, body.resolution_note or "")
    await db.refresh(call)

    return SuccessResponse(
        data=_call_to_message_record(call),
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/{message_id}/forward",
    response_model=SuccessResponse[dict],
    summary="Forward message",
    description="Forward message to email destinations.",
)
async def forward_message(
    message_id: uuid.UUID,
    body: MessageForwardRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict]:
    """Forward message to destinations."""
    svc = MessageService(db, tenant.id)
    try:
        call = await svc.forward_message(message_id, body.destinations)
        await db.refresh(call)
    except ValueError:
        raise HTTPException(status_code=404, detail="Message not found")

    logger.info(
        "message.forwarded",
        message_id=str(message_id),
        destinations=body.destinations,
    )

    return SuccessResponse(
        data={
            "message": f"Forwarded to {len(body.destinations)} destination(s)",
            "destinations": body.destinations,
            "note": body.note,
        },
        meta=ResponseMeta(request_id=""),
    )


@router.delete(
    "/{message_id}",
    response_model=SuccessResponse[dict],
    summary="Delete message",
    description="Soft-delete a message.",
)
async def delete_message(
    message_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict]:
    """Delete a message (sets voicemail_left = False)."""
    svc = MessageService(db, tenant.id)
    try:
        await svc.delete_message(message_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Message not found")

    return SuccessResponse(
        data={"message": "Message deleted successfully"},
        meta=ResponseMeta(request_id=""),
    )
