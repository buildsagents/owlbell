"""Celery tasks for analytics rollups."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import structlog

from workers.async_bridge import run_async
from workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="workers.rollup_yesterday", max_retries=2)
def rollup_yesterday() -> dict:
    """Roll up call metrics for yesterday (all tenants). Runs nightly via beat."""
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    return _execute_rollup(yesterday.isoformat())


@celery_app.task(name="workers.rollup_day", bind=True, max_retries=2)
def rollup_day(self, day_iso: str, tenant_id: str | None = None) -> dict:
    """Roll up metrics for a single calendar day."""
    try:
        return _execute_rollup(day_iso, tenant_id=tenant_id)
    except Exception as exc:
        logger.error("analytics.rollup_failed", rollup_date=day_iso, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


def _execute_rollup(day_iso: str, tenant_id: str | None = None) -> dict:
    from uuid import UUID

    from backend.db.session import open_db_session
    from backend.domain.analytics.rollup import rollup_all_tenants_for_day
    from workers.db import ensure_worker_db

    ensure_worker_db()

    rollup_date = date.fromisoformat(day_iso)
    tid = UUID(tenant_id) if tenant_id else None

    async def _run() -> dict:
        async with open_db_session() as db:
            result = await rollup_all_tenants_for_day(db, rollup_date, tenant_id=tid)
            await db.commit()
            return result

    result = run_async(_run())
    logger.info(
        "analytics.rollup_complete",
        rollup_date=day_iso,
        tenants=result.get("tenants"),
    )
    return result