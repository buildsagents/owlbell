"""workers/review_tasks.py — Post-job review requests (owlbell.txt #5).

Beat-scheduled task that finds recently *completed* appointments and texts the
customer a review link. Idempotent via ``Appointment.review_requested_at``.

Only appointments with a ``completed_at`` timestamp are considered, so enabling
this never blasts the historical backlog (that column is populated going
forward, when a job is marked completed).

Requires a per-tenant review link in ``tenant.config_json``:
    google_review_url    str   (required — skipped if absent)
    reviews_enabled      bool  (default True)
    review_min_delay_hours int (default 2 — wait after completion)
    review_max_age_hours   int (default 168 — don't ask about stale jobs)
    review_template      str   (default below; {name} {business} {url})
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID  # noqa: F401  (kept for parity/type hints in callers)

import structlog

from workers.async_bridge import run_async
from workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

_EVENT_TYPE = "review.request"

DEFAULT_MIN_DELAY_HOURS = 2
DEFAULT_MAX_AGE_HOURS = 168  # 7 days
# Coarse DB guard so the query never scans the whole completed history.
_QUERY_MAX_AGE_DAYS = 30

_DEFAULT_TEMPLATE = (
    "Hi {name}, thanks for choosing {business}. If you were happy with the "
    "work, a quick Google review would really help us: {url}"
)


@celery_app.task(name="workers.send_review_requests", max_retries=2)
def send_review_requests() -> dict[str, Any]:
    """Text a review link for appointments completed within the review window."""
    from workers.db import ensure_worker_db

    ensure_worker_db()
    return run_async(_send_review_requests())


def _as_utc(dt: datetime | None) -> datetime | None:
    """Normalize a possibly-naive DB timestamp to timezone-aware UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _review_due(appt: Any, tenant: Any, now: datetime) -> bool:
    """True when ``appt`` should get a review-request text (pure/testable)."""
    config = tenant.config_json or {}
    if not config.get("reviews_enabled", True):
        return False
    if not config.get("google_review_url"):
        return False
    if not appt.caller_number:
        return False
    completed = _as_utc(getattr(appt, "completed_at", None))
    if completed is None:
        return False
    min_delay = timedelta(hours=int(config.get("review_min_delay_hours", DEFAULT_MIN_DELAY_HOURS)))
    max_age = timedelta(hours=int(config.get("review_max_age_hours", DEFAULT_MAX_AGE_HOURS)))
    age = now - completed
    return min_delay <= age <= max_age


def _render_message(appt: Any, tenant: Any) -> str:
    config = tenant.config_json or {}
    template = config.get("review_template") or _DEFAULT_TEMPLATE
    return template.format(
        name=appt.caller_name or "there",
        business=tenant.business_name or tenant.name or "us",
        url=config.get("google_review_url", ""),
    )


async def _send_review_requests() -> dict[str, Any]:
    from sqlalchemy import select

    from backend.db.models.business import Appointment
    from backend.db.models.enums import AppointmentStatus
    from backend.db.models.tenant import Tenant
    from backend.db.session import open_db_session
    from backend.integrations.twilio import send_sms

    now = datetime.now(timezone.utc)
    coarse_floor = now - timedelta(days=_QUERY_MAX_AGE_DAYS)

    scanned = 0
    sent = 0
    skipped = 0

    async with open_db_session() as db:
        rows = (
            await db.execute(
                select(Appointment).where(
                    Appointment.status == AppointmentStatus.COMPLETED,
                    Appointment.review_requested_at.is_(None),
                    Appointment.completed_at.is_not(None),
                    Appointment.completed_at >= coarse_floor,
                )
            )
        ).scalars().all()

        if not rows:
            return {"scanned": 0, "sent": 0, "skipped": 0}

        tenant_ids = {a.tenant_id for a in rows}
        tenants = {
            t.id: t
            for t in (
                await db.execute(select(Tenant).where(Tenant.id.in_(tenant_ids)))
            ).scalars().all()
        }

        for appt in rows:
            scanned += 1
            tenant = tenants.get(appt.tenant_id)
            if tenant is None or not _review_due(appt, tenant, now):
                continue

            body = _render_message(appt, tenant)
            result = await send_sms(
                appt.caller_number,
                body,
                tenant_id=tenant.id,
                session_maker=open_db_session,
                event_type=_EVENT_TYPE,
                entity_id=appt.id,
                entity_type="appointment",
            )

            if result.get("success"):
                appt.review_requested_at = now
                sent += 1
            else:
                skipped += 1
                logger.warning(
                    "review.send_failed",
                    appointment_id=str(appt.id),
                    error=result.get("error"),
                )

        await db.commit()

    logger.info("review.batch_complete", scanned=scanned, sent=sent, skipped=skipped)
    return {"scanned": scanned, "sent": sent, "skipped": skipped}
