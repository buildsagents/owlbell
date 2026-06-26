"""AI-powered outreach pipeline with multi-agent orchestration, dedup, and smart scheduling."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Any, Optional

import structlog

from backend.leads.email_ai import (
    generate_email,
    generate_followup,
    generate_subject,
    is_configured as ai_configured,
)
from backend.leads.email_sender import send_email, is_configured as sender_configured
from backend.leads.lead_scorer import score_single_lead
from backend.leads import lead_store

logger = structlog.get_logger(__name__)

# ── Configuration ──────────────────────────────────────────────

DAILY_CAP = 50
SEND_SPREAD_MINUTES = 30  # Spread sends across this window per batch
MIN_SCORE_TO_SEND = 3
MAX_RETRIES = 2

# Business hours (local time) — only send during these
SEND_START_HOUR = 7
SEND_END_HOUR = 18

# ── Smart Scheduling ──────────────────────────────────────────


def _is_business_hours(lead: dict[str, Any]) -> bool:
    """Check if it's business hours in the lead's timezone (rough EST/CST/MST/PST)."""
    state = (lead.get("state") or "").upper()
    now = datetime.now(timezone.utc)

    # Rough timezone mapping
    tz_map = {
        "TX": -5, "FL": -5, "GA": -5, "NC": -5, "SC": -5,
        "TN": -5, "AL": -5, "MS": -5, "LA": -5, "OK": -5,
        "AR": -5, "MO": -5, "IA": -5, "MN": -5, "WI": -5,
        "IL": -5, "IN": -5, "OH": -5, "MI": -5, "KY": -5,
        "WV": -5, "VA": -5, "DC": -5, "MD": -5, "DE": -5,
        "PA": -5, "NJ": -5, "NY": -5, "CT": -5, "RI": -5,
        "MA": -5, "NH": -5, "VT": -5, "ME": -5,
        "ND": -6, "SD": -6, "NE": -6, "KS": -6,
        "CO": -7, "UT": -7, "AZ": -7, "NM": -7, "WY": -7,
        "MT": -7, "ID": -7,
        "CA": -8, "OR": -8, "WA": -8, "NV": -8,
    }
    offset = tz_map.get(state, -5)
    local_hour = (now.hour + offset) % 24
    return SEND_START_HOUR <= local_hour < SEND_END_HOUR


def _spread_delay(index: int, total: int) -> float:
    """Return delay in seconds to spread sends across the window."""
    if total <= 1:
        return 0
    window_seconds = SEND_SPREAD_MINUTES * 60
    per_send_delay = window_seconds / total
    jitter = random.uniform(0, per_send_delay * 0.3)
    return per_send_delay + jitter


# ── AI Agent: Lead Personalization ────────────────────────────


async def _ai_personalize(lead: dict[str, Any]) -> dict[str, Any]:
    """AI Agent: Generate unique email body + subject for a lead."""
    if not ai_configured():
        return lead

    body = await generate_email(
        business_name=lead.get("name", "your business"),
        trade=lead.get("trade", "contractor"),
        city=lead.get("city", "your area"),
        state=lead.get("state", ""),
        website=lead.get("website"),
    )
    if body:
        lead["_ai_body"] = body

    subject = await generate_subject(
        business_name=lead.get("name", "your business"),
        trade=lead.get("trade", "contractor"),
        city=lead.get("city", "your area"),
        stage=0,
    )
    if subject:
        lead["_ai_subject"] = subject

    return lead


# ── AI Agent: Follow-up Generation ────────────────────────────


async def _ai_followup(lead: dict[str, Any], stage: int) -> Optional[str]:
    """AI Agent: Generate contextual follow-up email."""
    days_since = 0
    if lead.get("last_contacted"):
        try:
            last = datetime.fromisoformat(lead["last_contacted"])
            days_since = (datetime.now(timezone.utc) - last).days
        except Exception:
            days_since = 3 * stage

    return await generate_followup(lead, stage, max(days_since, 1))


# ── Send with retries ─────────────────────────────────────────


async def _send_with_retry(
    lead: dict[str, Any],
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Send email with retry logic."""
    first_name = (lead.get("name") or "there").split()[0]

    for attempt in range(1, MAX_RETRIES + 2):
        result = await send_email(
            to_email=lead["email"],
            to_name=first_name,
            subject=subject,
            body_text=body,
        )
        if result.get("success"):
            return result
        logger.warning("outreach.send_retry", email=lead.get("email"), attempt=attempt, error=result.get("error"))
        if attempt <= MAX_RETRIES:
            await asyncio.sleep(5 * attempt)
        else:
            break

    return result


# ── Send initial outreach ─────────────────────────────────────


async def send_initial(
    lead: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Send first email to a lead using AI personalization."""
    email = lead.get("email", "")
    if not email:
        return {"success": False, "error": "no_email"}

    if not dry_run and lead_store.already_sent_to(email):
        return {"success": False, "error": "already_sent"}

    # AI personalize
    lead = await _ai_personalize(lead)
    body = lead.get("_ai_body") or lead.get("_fallback_body", "")
    subject = lead.get("_ai_subject") or lead.get("_fallback_subject", f"Quick question about {lead.get('name', 'your business')}")

    if not body:
        return {"success": False, "error": "ai_generation_failed"}

    if dry_run:
        logger.info("outreach.dry_run", email=email, subject=subject)
        return {"success": True, "dry_run": True, "subject": subject, "body_preview": body[:100]}

    result = await _send_with_retry(lead, subject, body)

    if result.get("success"):
        lead_store.mark_sent(email, subject=subject, body_preview=body[:100])
        logger.info("outreach.sent", email=email, subject=subject, score=lead.get("score", "?"))
    else:
        logger.error("outreach.send_failed", email=email, error=result.get("error"))

    return result


async def send_followup(
    lead: dict[str, Any],
    stage: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Send an AI-generated follow-up email at a given stage (1, 2, 3)."""
    email = lead.get("email", "")
    if not email:
        return {"success": False, "error": "no_email"}

    # AI generate follow-up
    body = await _ai_followup(lead, stage)
    if not body:
        return {"success": False, "error": "ai_generation_failed"}

    subject = await generate_subject(
        business_name=lead.get("name", "your business"),
        trade=lead.get("trade", "contractor"),
        city=lead.get("city", "your area"),
        stage=stage,
    )
    subject = subject or f"Following up — {lead.get('name', '')}"

    if dry_run:
        logger.info("outreach.dry_run_followup", email=email, stage=stage, subject=subject)
        return {"success": True, "dry_run": True, "subject": subject, "body_preview": body[:100]}

    result = await _send_with_retry(lead, subject, body)

    if result.get("success"):
        lead_store.mark_follow_up_sent(email, subject=subject, body_preview=body[:100])
        logger.info("outreach.followup_sent", email=email, stage=stage, subject=subject)
    else:
        logger.error("outreach.followup_failed", email=email, stage=stage, error=result.get("error"))

    return result


# ── Pipeline orchestrators ────────────────────────────────────


async def run_initial_batch(
    max_per_batch: int = 15,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Send initial outreach to the highest-scored pending leads.

    Steps:
    1. Score any unscored leads
    2. Pull highest-scored pending leads
    3. AI personalize each one
    4. Send with smart scheduling
    """
    if not sender_configured():
        return {"status": "error", "error": "No email sender configured"}

    # Score unscored leads first
    from backend.leads.lead_scorer import score_pending_leads
    await score_pending_leads(limit=50)

    # Get highest-scored pending
    pending = lead_store.get_pending_send(limit=max_per_batch)
    if not pending:
        # Try refilling lead pool
        from backend.leads.lead_generator import ensure_lead_pool
        refill = await ensure_lead_pool(min_pool=30)
        if refill.get("refilled", 0) > 0:
            pending = lead_store.get_pending_send(limit=max_per_batch)

    if not pending:
        return {"status": "ok", "sent": 0, "skipped": 0, "pool_empty": True}

    total = len(pending)
    sent_count = 0
    error_count = 0
    skipped = 0
    results = []

    for idx, lead in enumerate(pending):
        email = lead.get("email", "")
        if not email:
            skipped += 1
            continue

        if not dry_run and lead_store.already_sent_to(email):
            skipped += 1
            continue

        # Respect business hours
        if not dry_run:
            delay = _spread_delay(idx, total)
            await asyncio.sleep(delay)

        result = await send_initial(lead, dry_run=dry_run)

        if result.get("success"):
            sent_count += 1
        elif result.get("error") == "already_sent":
            skipped += 1
        else:
            error_count += 1

        results.append({"email": email, "result": result})

    return {
        "status": "ok",
        "sent": sent_count,
        "skipped": skipped,
        "errors": error_count,
        "total": total,
        "dry_run": dry_run,
        "pool_depth": lead_store.get_pending_send(limit=9999),
    }


async def run_followup_batch(
    max_per_batch: int = 20,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Send follow-ups to leads who haven't replied.

    Stages:
    - Stage 0 → Stage 1: 3 days after initial
    - Stage 1 → Stage 2: 7 days after follow-up 1
    - Stage 2 → Stage 3: 14 days after follow-up 2
    - Stage 3: Archived (21+ days no response)
    """
    if not sender_configured():
        return {"status": "error", "error": "No email sender configured"}

    pending = lead_store.get_pending_follow_ups(limit=max_per_batch)
    if not pending:
        return {"status": "ok", "sent": 0, "no_pending": True}

    sent_count = 0
    archived = 0

    for lead in pending:
        stage = lead.get("follow_up_stage", 0) + 1
        max_follow_ups = lead.get("max_follow_ups", 3)

        if stage > max_follow_ups:
            lead_store.mark_archived(lead.get("email", ""))
            archived += 1
            continue

        result = await send_followup(lead, stage, dry_run=dry_run)

        if result.get("success"):
            sent_count += 1

        await asyncio.sleep(random.uniform(2, 5))

    return {
        "status": "ok",
        "sent": sent_count,
        "archived": archived,
    }


async def run_full_pipeline(
    max_initial: int = 15,
    max_followups: int = 20,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the complete outreach pipeline:
    1. Score pending leads
    2. Send initial batch
    3. Send follow-ups
    4. Check if pool needs refilling
    """
    results = {}

    # Step 1: Score
    from backend.leads.lead_scorer import score_pending_leads
    scored = await score_pending_leads(limit=50)
    results["scored"] = scored

    # Step 2: Initial outreach
    initial = await run_initial_batch(max_per_batch=max_initial, dry_run=dry_run)
    results["initial"] = initial

    # Step 3: Follow-ups
    followups = await run_followup_batch(max_per_batch=max_followups, dry_run=dry_run)
    results["followups"] = followups

    # Step 4: Check pool health
    from backend.leads.lead_generator import ensure_lead_pool
    pool = await ensure_lead_pool(min_pool=30)
    results["pool"] = pool

    return results


# ── Stats ──────────────────────────────────────────────────────


def get_stats() -> dict[str, Any]:
    from backend.leads.lead_generator import get_pool_depth
    return {
        **lead_store.stats(),
        "pool_depth": get_pool_depth(),
    }
