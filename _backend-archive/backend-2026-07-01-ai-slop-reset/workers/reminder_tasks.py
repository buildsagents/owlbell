"""workers/reminder_tasks.py — Appointment reminder texts (owlbell.txt #3).

Beat-scheduled task that finds appointments entering their lead-time window
(default 24h before start) and sends a single reminder SMS to the caller.

Idempotent via ``Appointment.reminder_sent_at`` — the first beat tick that
sees an appointment inside the window sends the text and stamps the column, so
later ticks skip it. No schema change is required.

Per-tenant overrides live in ``tenant.config_json``:
    reminders_enabled   bool  (default True)
    reminder_lead_hours int   (default 24)
    reminder_template   str   (default below; supports {name} {business}
                               {date} {time} {phone} placeholders)
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog

from workers.async_bridge import run_async
from workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Notification event type — mirrors NotificationEventType.APPOINTMENT_REMINDER.
_EVENT_TYPE = "appointment.reminder"

DEFAULT_LEAD_HOURS = 24
# Coarse DB date pre-filter buffer (days), wide enough to cover any timezone
# offset so the precise per-appointment window check happens in Python.
_DATE_BUFFER_DAYS = 2

_DEFAULT_TEMPLATE = (
    "Hi {name}, a quick reminder from {business}: your appointment is on "
    "{date} at {time}. Reply Y to confirm, or call {phone} to rearrange."
)
_DEFAULT_TEMPLATE_NO_PHONE = (
    "Hi {name}, a quick reminder from {business}: your appointment is on "
    "{date} at {time}. Reply Y to confirm."
)


@celery_app.task(name="workers.send_appointment_reminders", max_retries=2)
def send_appointment_reminders() -> dict[str, Any]:
    """Send reminder texts for appointments entering their lead-time window."""
    from workers.db import ensure_worker_db

    ensure_worker_db()
    return run_async(_send_reminders())


def _resolve_tz(name: Optional[str]) -> Any:
    try:
        return ZoneInfo(name) if name else timezone.utc
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def _appointment_start_utc(appt: Any, fallback_tz: Optional[str]) -> Optional[datetime]:
    """Return the appointment's start as a timezone-aware UTC datetime."""
    tz = _resolve_tz(appt.timezone or fallback_tz)
    try:
        local_dt = datetime.combine(
            appt.scheduled_date, appt.start_time or time(0, 0), tzinfo=tz
        )
    except (TypeError, ValueError):
        return None
    return local_dt.astimezone(timezone.utc)


def _format_time(t: time) -> str:
    # UK-style lowercase am/pm with no leading zero, e.g. "2:30pm".
    # Avoids platform-specific %-I / %#I by stripping the zero manually.
    return t.strftime("%I:%M%p").lstrip("0").lower()


def _reminder_due(appt: Any, tenant: Any, now: datetime) -> bool:
    """True when ``appt`` should get a reminder text at ``now`` (pure/testable)."""
    config = tenant.config_json or {}
    if not config.get("reminders_enabled", True):
        return False
    if not appt.caller_number:
        return False
    start = _appointment_start_utc(appt, tenant.business_timezone)
    if start is None:
        return False
    lead_hours = int(config.get("reminder_lead_hours", DEFAULT_LEAD_HOURS))
    delta = start - now
    # Fire once the appointment is inside the lead window and still in the future.
    return timedelta(0) < delta <= timedelta(hours=lead_hours)


def _render_message(appt: Any, tenant: Any) -> str:
    config = tenant.config_json or {}
    business = tenant.business_name or tenant.name or "us"
    phone = tenant.business_phone or ""
    template = config.get("reminder_template") or (
        _DEFAULT_TEMPLATE if phone else _DEFAULT_TEMPLATE_NO_PHONE
    )
    d = appt.scheduled_date
    return template.format(
        name=appt.caller_name or "there",
        business=business,
        date=f"{d:%A} {d.day} {d:%B}",
        time=_format_time(appt.start_time or time(0, 0)),
        phone=phone,
    )


async def _send_reminders() -> dict[str, Any]:
    from sqlalchemy import select

    from backend.db.models.business import Appointment
    from backend.db.models.enums import AppointmentStatus
    from backend.db.models.tenant import Tenant
    from backend.db.session import open_db_session
    from backend.integrations.twilio import send_sms

    now = datetime.now(timezone.utc)
    lo = now.date() - timedelta(days=1)
    hi = now.date() + timedelta(days=_DATE_BUFFER_DAYS)

    scanned = 0
    sent = 0
    skipped = 0

    async with open_db_session() as db:
        rows = (
            await db.execute(
                select(Appointment).where(
                    Appointment.status.in_(
                        [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]
                    ),
                    Appointment.reminder_sent_at.is_(None),
                    Appointment.scheduled_date >= lo,
                    Appointment.scheduled_date <= hi,
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
            if tenant is None:
                continue

            if not _reminder_due(appt, tenant, now):
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
                appt.reminder_sent_at = now
                sent += 1
            else:
                skipped += 1
                logger.warning(
                    "reminder.send_failed",
                    appointment_id=str(appt.id),
                    error=result.get("error"),
                )

        await db.commit()

    logger.info("reminder.batch_complete", scanned=scanned, sent=sent, skipped=skipped)
    return {"scanned": scanned, "sent": sent, "skipped": skipped}
