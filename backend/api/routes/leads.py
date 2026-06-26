"""Lead pipeline routes — AI-powered outreach with scoring, scheduling, and auto-refill."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.leads import lead_store
from backend.leads.outreach import run_initial_batch, run_followup_batch, run_full_pipeline, get_stats
from backend.leads.lead_scorer import score_pending_leads
from backend.leads.lead_generator import (
    discover_new_leads,
    ensure_lead_pool,
    get_pool_depth,
    discover_untapped_markets,
)
from backend.leads.reply_handler import handle_replies

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

CRON_SECRET = os.getenv("LEADS_CRON_SECRET", "")


def _verify_secret(secret: Optional[str] = None) -> None:
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="LEADS_CRON_SECRET not configured")
    if secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")


@router.post("/run")
async def run_pipeline(
    mode: str = Query("full", description="'full', 'initial', 'followup', 'score', 'discover'"),
    max_initial: int = Query(15, description="Max initial emails to send"),
    max_followups: int = Query(20, description="Max follow-ups to send"),
    dry_run: bool = Query(False, description="Simulate without sending"),
    secret: Optional[str] = Query(None),
):
    """Run the outreach pipeline. Requires cron secret."""
    _verify_secret(secret)

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
async def check_replies_endpoint(secret: Optional[str] = Query(None)):
    """Check inbox for replies and auto-respond with AI."""
    _verify_secret(secret)
    return await handle_replies()


@router.get("/all")
async def get_all_leads(secret: Optional[str] = Query(None)):
    """Get all leads with full history."""
    _verify_secret(secret)
    return {"leads": lead_store.get_all_leads(), "stats": lead_store.stats()}


@router.get("/stats")
async def pipeline_stats(secret: Optional[str] = Query(None)):
    """Get pipeline statistics."""
    _verify_secret(secret)
    return get_stats()


@router.get("/pool")
async def pool_health(secret: Optional[str] = Query(None)):
    """Check lead pool health and upcoming markets."""
    _verify_secret(secret)
    queue = await discover_untapped_markets()
    return {
        "pool_depth": get_pool_depth(),
        "low": get_pool_depth() < 30,
        "total_in_store": lead_store.get_lead_count(),
        "pending_send": len(lead_store.get_pending_send(limit=9999)),
        "markets_remaining": len(queue),
        "next_markets": queue[:5],
    }
