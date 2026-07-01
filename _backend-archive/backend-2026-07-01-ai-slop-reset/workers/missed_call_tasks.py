"""workers/missed_call_tasks.py — Missed-call text-back (AI Ops module P1).

The wedge module: when an inbound call is missed (no answer, failed, or went
to voicemail), text the caller straight back so the lead doesn't leak to a
competitor. Runs on a 1-minute beat for a near-instant reply.

Idempotent via ``Call.metadata_json["text_back_sent_at"]`` — no schema change.

Per-tenant overrides in ``tenant.config_json``:
    missed_call_textback_enabled  bool (default True)
    missed_call_max_age_minutes   int  (default 360 — don't text about stale calls)
    missed_call_template          str  ({name} {business})
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from backend.db.models.enums import CallDirection, CallStatus
from workers.async_bridge import run_async
from workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

_EVENT_TYPE = "missed_call.textback"

DEFAULT_MAX_AGE_MINUTES = 360  # 6h
# Coarse DB guard so the sweep never scans the whole call history.
_QUERY_MAX_AGE_HOURS = 24

# A call the caller was NOT helped on.
_MISSED_STATUSES = {CallStatus.NO_ANSWER, CallStatus.FAILED, CallStatus.VOICEMAIL}

_DEFAULT_TEMPLATE = (
    "Hi {name}, this is {business}. Sorry we missed your call. Reply here "
    "with what you need and we'll get straight back to you."
)


@celery_app.task(name="workers.send_missed_call_textbacks", max_retries=2)
def send_missed_call_textbacks() -> dict[str, Any]:
    """Text back callers whose inbound call was missed."""
    from workers.db import ensure_worker_db

    ensure_worker_db()
    return run_async(_send_textbacks())


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _is_missed(call: Any) -> bool:
    return bool(getattr(call, "voicemail_left", False)) or call.status in _MISSED_STATUSES


def _textback_due(call: Any, tenant: Any, now: datetime) -> bool:
    """True when a missed inbound call should get a text-back (pure/testable)."""
    config = tenant.config_json or {}
    if not config.get("missed_call_textback_enabled", True):
        return False
    if call.direction != CallDirection.INBOUND:
        return False
    if not call.caller_number:
        return False
    if (call.metadata_json or {}).get("text_back_sent_at"):
        return False
    if not _is_missed(call):
        return False
    started = _as_utc(call.started_at)
    if started is None:
        return False
    max_age = timedelta(
        minutes=int(config.get("missed_call_max_age_minutes", DEFAULT_MAX_AGE_MINUTES))
    )
    return (now - started) <= max_age


def _render_message(call: Any, tenant: Any) -> str:
    config = tenant.config_json or {}
    template = config.get("missed_call_template") or _DEFAULT_TEMPLATE
    return template.format(
        name=call.caller_name or "there",
        business=tenant.business_name or tenant.name or "us",
    )


async def _send_textbacks() -> dict[str, Any]:
    from sqlalchemy import or_, select

    from backend.db.models.call import Call
    from backend.db.models.tenant import Tenant
    from backend.db.session import open_db_session
    from backend.integrations.twilio import send_sms

    now = datetime.now(timezone.utc)
    coarse_floor = now - timedelta(hours=_QUERY_MAX_AGE_HOURS)

    scanned = 0
    sent = 0
    skipped = 0

    async with open_db_session() as db:
        rows = (
            await db.execute(
                select(Call).where(
                    Call.direction == CallDirection.INBOUND,
                    Call.started_at >= coarse_floor,
                    or_(
                        Call.status.in_(list(_MISSED_STATUSES)),
                        Call.voicemail_left.is_(True),
                    ),
                )
            )
        ).scalars().all()

        if not rows:
            return {"scanned": 0, "sent": 0, "skipped": 0}

        tenant_ids = {c.tenant_id for c in rows}
        tenants = {
            t.id: t
            for t in (
                await db.execute(select(Tenant).where(Tenant.id.in_(tenant_ids)))
            ).scalars().all()
        }

        for call in rows:
            scanned += 1
            tenant = tenants.get(call.tenant_id)
            if tenant is None or not _textback_due(call, tenant, now):
                continue

            body = _render_message(call, tenant)
            result = await send_sms(
                call.caller_number,
                body,
                tenant_id=tenant.id,
                session_maker=open_db_session,
                event_type=_EVENT_TYPE,
                entity_id=call.id,
                entity_type="call",
            )

            if result.get("success"):
                # Reassign (not mutate) so SQLAlchemy detects the JSONB change.
                call.metadata_json = {
                    **(call.metadata_json or {}),
                    "text_back_sent_at": now.isoformat(),
                }
                sent += 1
            else:
                skipped += 1
                logger.warning(
                    "missed_call.textback_failed",
                    call_id=str(call.id),
                    error=result.get("error"),
                )

        await db.commit()

    logger.info("missed_call.batch_complete", scanned=scanned, sent=sent, skipped=skipped)
    return {"scanned": scanned, "sent": sent, "skipped": skipped}
