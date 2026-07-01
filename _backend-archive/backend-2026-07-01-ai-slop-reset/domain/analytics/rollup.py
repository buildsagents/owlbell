"""Nightly analytics rollups — pre-aggregate daily tenant metrics."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.analytics import AnalyticsDailyRollup
from backend.db.models.tenant import Tenant
from backend.domain.analytics.metrics import compute_period_metrics


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc).replace(tzinfo=None)
    end = start + timedelta(days=1)
    return start, end


async def rollup_tenant_day(
    session: AsyncSession,
    tenant_id: UUID,
    rollup_date: date,
) -> dict[str, Any]:
    """Compute and upsert one tenant-day rollup row."""
    start, end = _day_bounds(rollup_date)
    metrics = await compute_period_metrics(session, tenant_id, start, end)
    now = datetime.utcnow()

    stmt = insert(AnalyticsDailyRollup).values(
        tenant_id=tenant_id,
        rollup_date=rollup_date,
        total_calls=metrics["total_calls"],
        answered_calls=metrics["answered_calls"],
        missed_calls=metrics["missed_calls"],
        ai_handled_calls=metrics["ai_handled_calls"],
        total_duration_seconds=metrics["total_duration_seconds"],
        duration_count=metrics["duration_count"],
        total_wait_seconds=metrics["total_wait_seconds"],
        wait_count=metrics["wait_count"],
        rolled_up_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_analytics_daily_tenant_date",
        set_={
            "total_calls": stmt.excluded.total_calls,
            "answered_calls": stmt.excluded.answered_calls,
            "missed_calls": stmt.excluded.missed_calls,
            "ai_handled_calls": stmt.excluded.ai_handled_calls,
            "total_duration_seconds": stmt.excluded.total_duration_seconds,
            "duration_count": stmt.excluded.duration_count,
            "total_wait_seconds": stmt.excluded.total_wait_seconds,
            "wait_count": stmt.excluded.wait_count,
            "rolled_up_at": now,
        },
    )
    await session.execute(stmt)
    return {"tenant_id": str(tenant_id), "rollup_date": rollup_date.isoformat(), **metrics}


async def rollup_all_tenants_for_day(
    session: AsyncSession,
    rollup_date: date,
    *,
    tenant_id: Optional[UUID] = None,
) -> dict[str, Any]:
    """Roll up metrics for every active tenant (or one tenant) for a calendar day."""
    if tenant_id is not None:
        tenant_ids = [tenant_id]
    else:
        rows = await session.execute(select(Tenant.id))
        tenant_ids = list(rows.scalars().all())

    results = []
    for tid in tenant_ids:
        results.append(await rollup_tenant_day(session, tid, rollup_date))

    return {"rollup_date": rollup_date.isoformat(), "tenants": len(results), "rows": results}


async def fetch_daily_rollups(
    session: AsyncSession,
    tenant_id: UUID,
    start: date,
    end: date,
) -> dict[str, AnalyticsDailyRollup]:
    """Return rollup rows keyed by ISO date string for [start, end)."""
    rows = await session.execute(
        select(AnalyticsDailyRollup).where(
            AnalyticsDailyRollup.tenant_id == tenant_id,
            AnalyticsDailyRollup.rollup_date >= start,
            AnalyticsDailyRollup.rollup_date < end,
        )
    )
    return {r.rollup_date.isoformat(): r for r in rows.scalars().all()}


def rollup_row_to_daily_entry(row: AnalyticsDailyRollup) -> dict[str, Any]:
    avg_dur = (
        round(row.total_duration_seconds / row.duration_count, 1)
        if row.duration_count
        else 0
    )
    return {
        "date": row.rollup_date.isoformat(),
        "calls": row.total_calls,
        "answered": row.answered_calls,
        "missed": row.missed_calls,
        "avg_duration": avg_dur,
        "source": "rollup",
    }