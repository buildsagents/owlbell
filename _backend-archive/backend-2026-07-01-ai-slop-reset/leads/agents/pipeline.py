from __future__ import annotations

from typing import Any, Optional

import structlog

from backend.leads import lead_store
from backend.leads.agents.company_intelligence import CompanyIntelligenceAgent
from backend.leads.agents.signals import SignalAgent
from backend.leads.agents.opportunity import OpportunityAgent
from backend.leads.agents.personalisation import PersonalisationAgent
from backend.leads.agents.outreach import OutreachAgent

logger = structlog.get_logger(__name__)

# Fields produced by the agent pipeline that must survive to the send step.
# Without this write-back, get_leads_ready_for_outreach never matches and the
# whole agent pipeline is computed and discarded.
_PERSISTED_FIELDS = (
    "_intelligence",
    "_intel_status",
    "_intel_extracted_at",
    "_signals",
    "_missed_call_risk",
    "_signal_score",
    "_opportunity",
    "_opportunity_qualified",
    "_opportunity_confidence",
    "_opportunity_approach",
    "_personalisation",
    "_outreach",
    "industry",
    "ai_fit_score",
    "has_emergency_service",
    "has_online_booking",
    "phone_prominence",
    "estimated_call_volume",
    "website_quality",
    "business_size",
    "services",
    "reviews",
    "opening_hours",
)


def _persist_enrichment(leads: list[dict[str, Any]]) -> int:
    """Write agent enrichment back to the lead store, keyed by email."""
    saved = 0
    for lead in leads:
        email = lead.get("email")
        if not email:
            continue
        payload = {k: lead[k] for k in _PERSISTED_FIELDS if k in lead}
        if not payload:
            continue
        try:
            lead_store.update_lead(email, **payload)
            saved += 1
        except Exception as exc:  # best-effort; one bad lead shouldn't abort the batch
            logger.error("pipeline.persist_error", email=email, error=str(exc))
    return saved


async def run_intel_pipeline(
    leads: list[dict[str, Any]],
    max_leads: int = 10,
    min_fit_score: float = 0.0,
) -> list[dict[str, Any]]:
    """Run Company Intelligence + Signal + Opportunity agents on a list of leads."""
    intel_agent = CompanyIntelligenceAgent()
    signal_agent = SignalAgent()
    opp_agent = OpportunityAgent()
    pers_agent = PersonalisationAgent()
    out_agent = OutreachAgent()

    enriched = await intel_agent.analyze_many(leads, max_concurrent=max_leads)
    logger.info("pipeline.intel_complete", count=len(enriched))

    # Detect observable buying triggers (review-text mining, after-hours gaps).
    # Deterministic + free; folds triggers into intelligence observations so the
    # downstream LLM agents reference real evidence, not invented details.
    enriched = signal_agent.detect_many(enriched)
    logger.info("pipeline.signals_complete", count=len(enriched))

    qualified = await opp_agent.evaluate_many(enriched, min_score=min_fit_score)
    logger.info("pipeline.opportunity_complete", count=len(qualified))

    personalised = await pers_agent.generate_many(qualified)
    logger.info("pipeline.personalisation_complete", count=len(personalised))

    with_outreach = await out_agent.generate_many(personalised)
    logger.info("pipeline.outreach_complete", count=len(with_outreach))

    saved = _persist_enrichment(with_outreach)
    logger.info("pipeline.persisted", count=saved)

    return with_outreach


def extract_qualified_leads(
    leads: list[dict[str, Any]],
    min_confidence: float = 0.5,
) -> list[dict[str, Any]]:
    return [
        l for l in leads
        if l.get("_opportunity", {}).get("qualified")
        and (l.get("_opportunity_confidence", 0) or 0) >= min_confidence
    ]
