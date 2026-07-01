"""workers/report_tasks.py — Weekly Ops Report email (owlbell blueprint P1).

Runs Monday mornings: for every tenant, aggregate the previous 7 days and email
the owner a plain-text value/leakage report. Read-only aggregation; delivery is
config-guarded (skipped when SendGrid isn't configured, so it's safe in dev).

Per-tenant overrides in ``tenant.config_json``:
    reports_enabled    bool  (default True)
    avg_job_value_gbp  float (default 250 — used for the opportunity estimate)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from workers.async_bridge import run_async
from workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="workers.generate_weekly_reports", max_retries=1)
def generate_weekly_reports() -> dict[str, Any]:
    """Build and email each tenant's weekly ops report."""
    from workers.db import ensure_worker_db

    ensure_worker_db()
    return run_async(_generate_weekly_reports())


async def _generate_weekly_reports() -> dict[str, Any]:
    from sqlalchemy import select

    from backend.business.reporting.service import (
        DEFAULT_AVG_JOB_VALUE_GBP,
        ReportingService,
        render_report_text,
    )
    from backend.db.models.tenant import Tenant
    from backend.db.session import open_db_session
    from backend.integrations.sendgrid.service import is_configured, send_email

    now = datetime.now(timezone.utc)
    end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)  # today 00:00 UTC
    start = end - timedelta(days=7)
    provider_ready = is_configured()

    scanned = 0
    sent = 0
    skipped = 0

    async with open_db_session() as db:
        tenants = (await db.execute(select(Tenant))).scalars().all()

        for tenant in tenants:
            scanned += 1
            config = tenant.config_json or {}
            if not config.get("reports_enabled", True):
                continue
            recipient = tenant.owner_email or tenant.business_email
            if not recipient:
                skipped += 1
                continue

            avg = float(config.get("avg_job_value_gbp", DEFAULT_AVG_JOB_VALUE_GBP))
            report = await ReportingService(db, tenant.id).build_weekly_report(
                start, end, avg_job_value=avg
            )
            business = tenant.business_name or tenant.name or "your business"
            body = render_report_text(report, business)
            subject = (
                f"Your Owlbell weekly report "
                f"({report['period_start']} to {report['period_end']})"
            )

            if not provider_ready:
                skipped += 1
                logger.info("weekly_report.skipped_no_provider", tenant_id=str(tenant.id))
                continue

            result = await send_email(recipient, business, subject, body)
            if result.get("success"):
                sent += 1
            else:
                skipped += 1
                logger.warning(
                    "weekly_report.email_failed",
                    tenant_id=str(tenant.id),
                    error=result.get("error"),
                )

    logger.info("weekly_report.batch_complete", scanned=scanned, sent=sent, skipped=skipped)
    return {"scanned": scanned, "sent": sent, "skipped": skipped}
