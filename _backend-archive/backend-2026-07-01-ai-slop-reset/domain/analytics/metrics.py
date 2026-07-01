"""Shared call-metric definitions for live queries and rollups."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.call import Call
from backend.db.models.enums import CallStatus

ANSWERED_STATUSES = (
    CallStatus.ANSWERED,
    CallStatus.ACTIVE,
    CallStatus.COMPLETED,
    CallStatus.TRANSFERRED,
)
MISSED_STATUSES = (
    CallStatus.NO_ANSWER,
    CallStatus.FAILED,
    CallStatus.VOICEMAIL,
)


async def compute_period_metrics(
    session: AsyncSession,
    tenant_id: UUID,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """Aggregate call metrics for a tenant over [start, end)."""
    base = (
        Call.tenant_id == tenant_id,
        Call.started_at >= start,
        Call.started_at < end,
    )

    total = (
        await session.execute(select(func.count(Call.id)).where(*base))
    ).scalar() or 0

    answered = (
        await session.execute(
            select(func.count(Call.id)).where(*base, Call.status.in_(ANSWERED_STATUSES))
        )
    ).scalar() or 0

    missed = (
        await session.execute(
            select(func.count(Call.id)).where(*base, Call.status.in_(MISSED_STATUSES))
        )
    ).scalar() or 0

    ai_count = (
        await session.execute(
            select(func.count(Call.id)).where(*base, Call.ai_handled.is_(True))
        )
    ).scalar() or 0

    dur_row = (
        await session.execute(
            select(
                func.coalesce(func.sum(Call.duration_seconds), 0),
                func.count(Call.id),
            ).where(*base, Call.duration_seconds.isnot(None))
        )
    ).one()

    wait_row = (
        await session.execute(
            select(
                func.coalesce(
                    func.sum(func.extract("epoch", Call.answered_at - Call.started_at)),
                    0,
                ),
                func.count(Call.id),
            ).where(*base, Call.answered_at.isnot(None))
        )
    ).one()

    total_duration = int(dur_row[0] or 0)
    duration_count = int(dur_row[1] or 0)
    total_wait = float(wait_row[0] or 0)
    wait_count = int(wait_row[1] or 0)

    avg_dur = round(total_duration / duration_count, 1) if duration_count else 0.0
    avg_wait = round(total_wait / wait_count, 1) if wait_count else 0.0
    resolution_rate = round(ai_count / total, 4) if total else 0.0

    return {
        "total_calls": total,
        "answered_calls": answered,
        "missed_calls": missed,
        "ai_handled_calls": ai_count,
        "total_duration_seconds": total_duration,
        "duration_count": duration_count,
        "total_wait_seconds": total_wait,
        "wait_count": wait_count,
        "avg_duration": avg_dur,
        "avg_wait_time": avg_wait,
        "resolution_rate": resolution_rate,
    }