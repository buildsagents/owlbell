"""api/routes/analytics.py - Dashboard analytics metrics."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import DBSession
from api.schemas.base import ResponseMeta, SuccessResponse
from backend.db.models.call import Call
from backend.db.models.enums import CallStatus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/analytics", tags=["Analytics"])

_PERIOD_DAYS = {"today": 1, "week": 7, "month": 30, "quarter": 90, "year": 365}

_ANSWERED_STATUSES = (
    CallStatus.ANSWERED,
    CallStatus.ACTIVE,
    CallStatus.COMPLETED,
    CallStatus.TRANSFERRED,
)
_MISSED_STATUSES = (
    CallStatus.NO_ANSWER,
    CallStatus.FAILED,
    CallStatus.VOICEMAIL,
    CallStatus.BUSY,
)


async def _compute_metrics(session: AsyncSession, start: datetime, end: datetime) -> dict[str, Any]:
    total_q = select(func.count(Call.id)).where(Call.started_at >= start, Call.started_at < end)
    total = (await session.execute(total_q)).scalar() or 0

    answered_q = (
        select(func.count(Call.id))
        .where(Call.started_at >= start, Call.started_at < end, Call.status.in_(_ANSWERED_STATUSES))
    )
    answered = (await session.execute(answered_q)).scalar() or 0

    missed_q = (
        select(func.count(Call.id))
        .where(Call.started_at >= start, Call.started_at < end, Call.status.in_(_MISSED_STATUSES))
    )
    missed = (await session.execute(missed_q)).scalar() or 0

    avg_dur_q = (
        select(func.avg(Call.duration_seconds))
        .where(Call.started_at >= start, Call.started_at < end, Call.duration_seconds.isnot(None))
    )
    avg_dur = (await session.execute(avg_dur_q)).scalar()
    avg_dur = round(float(avg_dur), 1) if avg_dur is not None else 0

    avg_wait_q = (
        select(func.avg(func.extract("epoch", Call.answered_at - Call.started_at)))
        .where(Call.started_at >= start, Call.started_at < end, Call.answered_at.isnot(None))
    )
    avg_wait = (await session.execute(avg_wait_q)).scalar()
    avg_wait = round(float(avg_wait), 1) if avg_wait is not None else 0

    ai_q = (
        select(func.count(Call.id))
        .where(Call.started_at >= start, Call.started_at < end, Call.ai_handled.is_(True))
    )
    ai_count = (await session.execute(ai_q)).scalar() or 0
    resolution_rate = round(ai_count / total, 4) if total > 0 else 0.0

    return {
        "total_calls": total,
        "answered_calls": answered,
        "missed_calls": missed,
        "avg_duration": avg_dur,
        "avg_wait_time": avg_wait,
        "resolution_rate": resolution_rate,
    }


def _compute_change(current: float | int, previous: float | int) -> float:
    if previous == 0:
        return 0.0
    return round(((current - previous) / previous) * 100, 1)


@router.get("/metrics")
async def get_metrics(
    request: Request,
    session: AsyncSession = DBSession,
    period: str = Query("week"),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
) -> SuccessResponse[dict]:
    now = datetime.now(timezone.utc)
    days = _PERIOD_DAYS.get(period, 7)

    if from_:
        start = datetime.fromisoformat(from_)
        end = datetime.fromisoformat(to) if to else now
    else:
        start = now - timedelta(days=days)
        end = now

    prev_start = start - timedelta(days=days)
    prev_end = start

    current = await _compute_metrics(session, start, end)
    previous = await _compute_metrics(session, prev_start, prev_end)

    metrics = {
        "total_calls": current["total_calls"],
        "total_change": _compute_change(current["total_calls"], previous["total_calls"]),
        "answered_calls": current["answered_calls"],
        "answered_change": _compute_change(current["answered_calls"], previous["answered_calls"]),
        "missed_calls": current["missed_calls"],
        "missed_change": _compute_change(current["missed_calls"], previous["missed_calls"]),
        "avg_duration": current["avg_duration"],
        "avg_duration_change": _compute_change(current["avg_duration"], previous["avg_duration"]),
        "avg_wait_time": current["avg_wait_time"],
        "avg_wait_time_change": _compute_change(current["avg_wait_time"], previous["avg_wait_time"]),
        "resolution_rate": current["resolution_rate"],
        "resolution_rate_change": _compute_change(current["resolution_rate"], previous["resolution_rate"]),
    }

    hourly_q = (
        select(
            func.extract("hour", Call.started_at).label("hour"),
            func.count(Call.id).label("calls"),
            func.count(Call.id).filter(Call.status.in_(_ANSWERED_STATUSES)).label("answered"),
            func.count(Call.id).filter(Call.status.in_(_MISSED_STATUSES)).label("missed"),
        )
        .where(Call.started_at >= start, Call.started_at < end)
        .group_by(func.extract("hour", Call.started_at))
        .order_by(func.extract("hour", Call.started_at))
    )
    hourly_rows = (await session.execute(hourly_q)).all()
    hourly_map = {int(r.hour): r for r in hourly_rows}
    hourly_data = [
        {
            "hour": h,
            "calls": int(hourly_map[h].calls) if h in hourly_map else 0,
            "answered": int(hourly_map[h].answered) if h in hourly_map else 0,
            "missed": int(hourly_map[h].missed) if h in hourly_map else 0,
        }
        for h in range(24)
    ]

    daily_q = (
        select(
            func.date_trunc("day", Call.started_at).label("date"),
            func.count(Call.id).label("calls"),
            func.count(Call.id).filter(Call.status.in_(_ANSWERED_STATUSES)).label("answered"),
            func.count(Call.id).filter(Call.status.in_(_MISSED_STATUSES)).label("missed"),
            func.avg(Call.duration_seconds).label("avg_duration"),
        )
        .where(Call.started_at >= start, Call.started_at < end)
        .group_by(func.date_trunc("day", Call.started_at))
        .order_by(func.date_trunc("day", Call.started_at))
    )
    daily_rows = (await session.execute(daily_q)).all()
    date_map = {}
    for r in daily_rows:
        d = r.date
        if hasattr(d, "date"):
            d = d.date()
        date_map[d.isoformat()] = {
            "date": d.isoformat(),
            "calls": int(r.calls),
            "answered": int(r.answered),
            "missed": int(r.missed),
            "avg_duration": round(float(r.avg_duration), 1) if r.avg_duration is not None else 0,
        }

    num_dates = min(days, 30)
    daily_data = []
    for i in range(num_dates):
        d = (start + timedelta(days=i)).date().isoformat()
        if d in date_map:
            daily_data.append(date_map[d])
        else:
            daily_data.append({
                "date": d,
                "calls": 0,
                "answered": 0,
                "missed": 0,
                "avg_duration": 0,
            })

    outcome_q = (
        select(Call.result, func.count(Call.id).label("count"))
        .where(Call.started_at >= start, Call.started_at < end, Call.result.isnot(None))
        .group_by(Call.result)
        .order_by(func.count(Call.id).desc())
    )
    outcome_rows = (await session.execute(outcome_q)).all()
    outcome_breakdown = [
        {
            "result": r.result.value if hasattr(r.result, "value") else str(r.result),
            "count": int(r.count),
        }
        for r in outcome_rows
    ]

    top_q = (
        select(Call.caller_number, func.count(Call.id).label("calls"))
        .where(Call.started_at >= start, Call.started_at < end)
        .group_by(Call.caller_number)
        .order_by(func.count(Call.id).desc())
        .limit(10)
    )
    top_rows = (await session.execute(top_q)).all()
    top_callers = [
        {"caller_number": r.caller_number, "calls": int(r.calls)}
        for r in top_rows
    ]

    payload: dict[str, Any] = {
        "metrics": metrics,
        "hourly_data": hourly_data,
        "daily_data": daily_data,
        "outcome_breakdown": outcome_breakdown,
        "top_callers": top_callers,
        "period": period,
        "date_range": {"from": start.isoformat(), "to": end.isoformat()},
    }

    request_id = getattr(getattr(request, "state", None), "request_id", None) or str(uuid.uuid4())[:11]
    return SuccessResponse(data=payload, meta=ResponseMeta(request_id=request_id))
