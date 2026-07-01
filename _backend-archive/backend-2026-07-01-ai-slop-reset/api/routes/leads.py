"""Lead pipeline routes — AI-powered outreach with scoring, scheduling, and auto-refill."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from backend.leads import lead_store
from backend.leads.outreach import run_initial_batch, run_followup_batch, run_full_pipeline, get_stats
from backend.leads.lead_scorer import score_pending_leads
from backend.leads.lead_generator import (
    discover_new_leads,
    ensure_lead_pool,
    get_pool_depth,
    discover_untapped_markets,
)
from backend.leads.agents import CompanyIntelligenceAgent, ConversationAgent, OnboardingAgent
from backend.leads.agents.pipeline import run_intel_pipeline, extract_qualified_leads
from backend.leads.reply_handler import handle_replies

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

CRON_SECRET = os.getenv("LEADS_CRON_SECRET", "")


def _verify_cron_secret(request: Request) -> None:
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="LEADS_CRON_SECRET not configured")

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        secret = auth[7:]
    else:
        secret = request.headers.get("X-Cron-Secret", "")

    if secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")


@router.post("/run")
async def run_pipeline(
    request: Request,
    mode: str = Query("full", description="'full', 'initial', 'followup', 'score', 'discover'"),
    max_initial: int = Query(15, description="Max initial emails to send"),
    max_followups: int = Query(20, description="Max follow-ups to send"),
    dry_run: bool = Query(False, description="Simulate without sending"),
):
    """Run the outreach pipeline. Requires cron secret."""
    _verify_cron_secret(request)

    if mode == "initial":
        return await run_initial_batch(max_per_batch=max_initial, dry_run=dry_run)
    elif mode == "followup":
        return await run_followup_batch(max_per_batch=max_followups, dry_run=dry_run)
    elif mode == "score":
        scored = await score_pending_leads(limit=100)
        return {"status": "ok", "scored": scored}
    elif mode == "discover":
        new_leads = await discover_new_leads(max_per_search=10)
        return {"status": "ok", "new_leads": new_leads, "pool_depth": get_pool_depth()}
    elif mode == "refill":
        refill = await ensure_lead_pool(min_pool=50)
        return {"status": "ok", **refill}

    # Full pipeline
    results = await run_full_pipeline(
        max_initial=max_initial,
        max_followups=max_followups,
        dry_run=dry_run,
    )
    return {"status": "ok", "mode": "full", **results}


@router.post("/check-replies")
async def check_replies_endpoint(request: Request):
    """Check inbox for replies and auto-respond with AI."""
    _verify_cron_secret(request)
    return await handle_replies()


@router.get("/all")
async def get_all_leads(request: Request):
    """Get all leads with full history."""
    _verify_cron_secret(request)
    return {"leads": lead_store.get_all_leads(), "stats": lead_store.stats()}


@router.get("/stats")
async def pipeline_stats(request: Request):
    """Get pipeline statistics."""
    _verify_cron_secret(request)
    return get_stats()


@router.get("/pool")
async def pool_health(request: Request):
    """Check lead pool health and upcoming markets."""
    _verify_cron_secret(request)
    queue = await discover_untapped_markets()
    return {
        "pool_depth": get_pool_depth(),
        "low": get_pool_depth() < 30,
        "total_in_store": lead_store.get_lead_count(),
        "pending_send": len(lead_store.get_pending_send(limit=9999)),
        "markets_remaining": len(queue),
        "next_markets": queue[:5],
    }


@router.post("/analyze")
async def analyze_lead(
    request: Request,
    name: str = Query(...),
    website: Optional[str] = Query(None),
):
    """Run Company Intelligence Agent on a single lead."""
    _verify_cron_secret(request)
    agent = CompanyIntelligenceAgent()
    result = await agent.analyze(business_name=name, website_url=website)
    return result


@router.post("/agent-pipeline")
async def agent_pipeline(
    request: Request,
    dry_run: bool = Query(True, description="If true, use sample lead instead of DB"),
    max_leads: int = Query(5, description="Max leads to process"),
    min_fit: float = Query(0.4, description="Minimum AI fit score to include"),
):
    """Run full agent pipeline: Intel -> Opportunity -> Personalisation -> Outreach."""
    _verify_cron_secret(request)

    if dry_run:
        from backend.leads import lead_store
        all_leads = lead_store.get_all_leads()[:max_leads]
        if not all_leads:
            all_leads = [
                {"name": "Absolute Plumbing", "website": "absoluteplumbing.com", "trade": "plumbing"},
                {"name": "Anchor Plumbing Co.", "website": "anchorplumbingco.com", "trade": "plumbing"},
            ]
    else:
        from backend.leads import lead_store
        all_leads = lead_store.get_leads_needing_scoring(limit=max_leads)

    result = await run_intel_pipeline(all_leads, max_leads=max_leads)

    qualified = extract_qualified_leads(result, min_confidence=min_fit)

    return {
        "status": "ok",
        "total_processed": len(result),
        "qualified": len(qualified),
        "qualified_names": [l.get("name") for l in qualified],
        "pipeline_complete": True,
    }


@router.post("/conversation")
async def conversation_endpoint(
    request: Request,
    name: str = Query(...),
    reply: str = Query(...),
    website: Optional[str] = Query(None),
):
    """Classify and respond to a reply using the Conversation Agent."""
    _verify_cron_secret(request)
    agent = ConversationAgent()

    intel_agent = CompanyIntelligenceAgent()
    result = await intel_agent.analyze(business_name=name, website_url=website)

    lead = {
        "name": name,
        "website": website or "",
        "_intelligence": result.get("intelligence"),
    }

    conv_result = await agent.handle_reply(lead, reply)
    return conv_result


@router.post("/onboard")
async def onboard_lead(
    request: Request,
    name: str = Query(...),
    email: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
):
    """Run Client Onboarding AI — provision Retell agent for a new customer."""
    _verify_cron_secret(request)

    lead = lead_store.get_lead_by_email(email) if email else None
    if not lead:
        lead = lead_store.get_lead_by_phone(phone) if phone else None
    if not lead:
        lead = {
            "name": name,
            "email": email or "",
            "phone": phone or "",
            "_intel_status": "pending",
        }

    agent = OnboardingAgent()
    result = await agent.provision(lead)
    return result
