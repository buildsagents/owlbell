"""workers/quote_tasks.py — Unaccepted-quote follow-ups (owlbell.txt #4).

Beat-scheduled task that chases quotes sitting in ``SENT`` — texting the
customer on a cadence until they accept, decline, or the quote expires or runs
out of follow-up attempts.

Per-tenant overrides live in ``tenant.config_json``:
    quote_followups_enabled      bool (default True)
    quote_followup_interval_hours int (default 48)
    quote_max_followups          int  (default 3)
    quote_followup_template      str  ({name} {business} {amount} {phone})
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from workers.async_bridge import run_async
from workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

_EVENT_TYPE = "quote.followup"

DEFAULT_INTERVAL_HOURS = 48
DEFAULT_MAX_FOLLOWUPS = 3
# Absolute guard so a misconfigured tenant can never text endlessly.
_HARD_MAX_FOLLOWUPS = 10

# Kept within the GSM-7 alphabet (no em dash) so messages stay single-segment;
# GBP amounts use the GSM-7-safe £ sign.
_DEFAULT_TEMPLATE = (
    "Hi {name}, following up on your quote from {business}{amount}. If you'd "
    "like to go ahead or have any questions, just reply{phone}."
)


@celery_app.task(name="workers.send_quote_followups", max_retries=2)
def send_quote_followups() -> dict[str, Any]:
    """Chase unaccepted quotes and expire ones past their expiry."""
    from workers.db import ensure_worker_db

    ensure_worker_db()
    return run_async(_send_quote_followups())


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _is_expired(quote: Any, now: datetime) -> bool:
    expires = _as_utc(getattr(quote, "expires_at", None))
    return expires is not None and now >= expires


def _followup_due(quote: Any, tenant: Any, now: datetime) -> bool:
    """True when a SENT quote is due for its next follow-up (pure/testable)."""
    config = tenant.config_json or {}
    if not config.get("quote_followups_enabled", True):
        return False
    if not quote.customer_number:
        return False
    if _is_expired(quote, now):
        return False

    max_followups = min(
        int(config.get("quote_max_followups", DEFAULT_MAX_FOLLOWUPS)), _HARD_MAX_FOLLOWUPS
    )
    if quote.followup_count >= max_followups:
        return False

    # Cadence anchored on the most recent touch (last follow-up, else sent).
    base = _as_utc(quote.last_followup_at) or _as_utc(quote.sent_at)
    if base is None:
        return False
    interval = timedelta(
        hours=int(config.get("quote_followup_interval_hours", DEFAULT_INTERVAL_HOURS))
    )
    return (now - base) >= interval


# UK-first business, so amounts default to GBP.
_CURRENCY_SYMBOLS = {"GBP": "£", "USD": "$", "EUR": "€"}


def _format_amount(quote: Any) -> str:
    if quote.amount is None:
        return ""
    symbol = _CURRENCY_SYMBOLS.get((getattr(quote, "currency", None) or "GBP").upper(), "")
    return f" for {symbol}{quote.amount:,.2f}"


def _render_message(quote: Any, tenant: Any) -> str:
    config = tenant.config_json or {}
    template = config.get("quote_followup_template") or _DEFAULT_TEMPLATE
    phone = tenant.business_phone or ""
    return template.format(
        name=quote.customer_name or "there",
        business=tenant.business_name or tenant.name or "us",
        amount=_format_amount(quote),
        phone=f" or call {phone}" if phone else "",
    )


async def _send_quote_followups() -> dict[str, Any]:
    from sqlalchemy import select

    from backend.db.models.business import Quote
    from backend.db.models.enums import QuoteStatus
    from backend.db.models.tenant import Tenant
    from backend.db.session import open_db_session
    from backend.integrations.twilio import send_sms

    now = datetime.now(timezone.utc)

    scanned = 0
    sent = 0
    expired = 0
    skipped = 0

    async with open_db_session() as db:
        rows = (
            await db.execute(
                select(Quote).where(
                    Quote.status == QuoteStatus.SENT,
                    Quote.followup_count < _HARD_MAX_FOLLOWUPS,
                )
            )
        ).scalars().all()

        if not rows:
            return {"scanned": 0, "sent": 0, "expired": 0, "skipped": 0}

        tenant_ids = {q.tenant_id for q in rows}
        tenants = {
            t.id: t
            for t in (
                await db.execute(select(Tenant).where(Tenant.id.in_(tenant_ids)))
            ).scalars().all()
        }

        for quote in rows:
            scanned += 1
            tenant = tenants.get(quote.tenant_id)
            if tenant is None:
                continue

            if _is_expired(quote, now):
                quote.status = QuoteStatus.EXPIRED
                expired += 1
                continue

            if not _followup_due(quote, tenant, now):
                continue

            body = _render_message(quote, tenant)
            result = await send_sms(
                quote.customer_number,
                body,
                tenant_id=tenant.id,
                session_maker=open_db_session,
                event_type=_EVENT_TYPE,
                entity_id=quote.id,
                entity_type="quote",
            )

            if result.get("success"):
                quote.followup_count += 1
                quote.last_followup_at = now
                sent += 1
            else:
                skipped += 1
                logger.warning(
                    "quote.followup_failed",
                    quote_id=str(quote.id),
                    error=result.get("error"),
                )

        await db.commit()

    logger.info(
        "quote.batch_complete", scanned=scanned, sent=sent, expired=expired, skipped=skipped
    )
    return {"scanned": scanned, "sent": sent, "expired": expired, "skipped": skipped}
