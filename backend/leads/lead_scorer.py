"""AI-powered lead scoring agent — scores contractors by conversion likelihood."""

from __future__ import annotations

from typing import Any

import structlog

from backend.leads.email_ai import score_lead, is_configured as ai_configured, generate_email
from backend.leads import lead_store

logger = structlog.get_logger(__name__)


def _heuristic_score(lead: dict[str, Any]) -> int:
    """Quick rule-based score (used when AI is unavailable)."""
    score = 5
    if lead.get("website"):
        score += 2
    if lead.get("phone"):
        score += 1
    if lead.get("rating", 0) >= 4.0:
        score += 1
    if lead.get("review_count", 0) >= 20:
        score += 1
    if lead.get("business_status") == "OPERATIONAL":
        score += 1
    if not lead.get("website"):
        score -= 1
    if lead.get("business_status") in ("CLOSED_TEMPORARILY", "CLOSED_PERMANENTLY"):
        score -= 2
    return max(1, min(10, score))


async def score_single_lead(lead: dict[str, Any]) -> int:
    """Score a single lead using AI, falling back to heuristics."""
    if not ai_configured():
        return _heuristic_score(lead)

    ai_score = await score_lead(lead)
    if ai_score is None or ai_score == 5:
        return _heuristic_score(lead)
    return ai_score


async def score_pending_leads(limit: int = 50) -> int:
    """Score all unscored leads in the store. Returns count scored."""
    unscored = lead_store.get_leads_needing_scoring(limit=limit)
    scored = 0

    for lead in unscored:
        email = lead.get("email", "")
        if not email:
            continue

        score = await score_single_lead(lead)
        lead_store.update_score(email, score)
        scored += 1

        if scored % 10 == 0:
            logger.info("scorer.progress", scored=scored, total=len(unscored))

    logger.info("scorer.complete", scored=scored, total=len(unscored))
    return scored


async def auto_personalize(lead: dict[str, Any]) -> dict[str, Any]:
    """Generate AI email body for a lead and store it."""
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
        lead_store.update_lead(lead.get("email", ""), _ai_body=body)
    return lead
