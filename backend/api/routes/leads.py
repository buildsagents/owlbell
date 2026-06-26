"""leads route — synchronous pipeline (split scrape/send to avoid Railway timeout)."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.leads.scraper import find_contractors, is_configured as scraper_configured
from backend.leads.email_finder import find_emails_for_leads
from backend.leads.outreach import send_initial_outreach, get_stats
from backend.leads.reply_handler import handle_replies
from backend.leads import lead_store

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

CRON_SECRET = os.getenv("LEADS_CRON_SECRET", "")


def _verify_secret(secret: Optional[str] = None) -> None:
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="LEADS_CRON_SECRET not configured")
    if secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")


@router.post("/run")
async def run_pipeline(
    mode: str = Query("initial", description="'initial' (scrape+sand), 'send' (send pending)"),
    trades: str = Query("hvac,plumbing,roofing,electrical"),
    cities: str = Query("Austin-TX,RoundRock-TX,CedarPark-TX"),
    max_leads: int = Query(80),
    max_outreach: int = Query(5, description="Max to send (keep low to avoid timeout)"),
    secret: Optional[str] = Query(None),
):
    """Scrape + find emails (mode=initial, fast) or send pending (mode=send, send pending)."""
    _verify_secret(secret)

    if mode == "send":
        pending = lead_store.get_pending_send()
        total_pending = len(pending)
        to_send = pending[:max_outreach]
        sent = 0
        errors = 0
        for lead in to_send:
            from backend.leads.outreach import send_initial

            result = await send_initial(lead, dry_run=False)
            if result.get("success"):
                lead_store.mark_sent(lead["email"])
                sent += 1
            else:
                errors += 1
            import asyncio
            await asyncio.sleep(1)
        return {"status": "ok", "mode": "send", "pending": total_pending, "sent": sent, "errors": errors}

    if not scraper_configured():
        return {"status": "error", "error": "Google Maps API key not configured"}

    city_list = []
    for part in cities.split(","):
        part = part.strip()
        if "-" in part:
            city, state = part.rsplit("-", 1)
            city_list.append({"city": city.strip(), "state": state.strip().upper()})

    trade_list = [t.strip() for t in trades.split(",")]

    leads = await find_contractors(trades=trade_list, cities=city_list, max_per_search=min(max_leads, 20))
    if not leads:
        return {"status": "error", "error": "No leads found"}

    leads_with_emails = await find_emails_for_leads(leads)
    with_email = [l for l in leads_with_emails if l.get("email")]

    result = {"leads_found": len(leads), "with_email": len(with_email)}

    if with_email and max_outreach > 0:
        outreach_results = await send_initial_outreach(with_email, max_per_day=max_outreach)
        sent_count = sum(1 for r in outreach_results if r.get("outreach_status") == "sent")
        result["emails_sent"] = sent_count
    else:
        result["emails_sent"] = 0

    return {"status": "ok", "mode": "initial", **result}


@router.post("/check-replies")
async def check_replies_endpoint(secret: Optional[str] = Query(None)):
    _verify_secret(secret)
    return await handle_replies()


@router.get("/all")
async def get_all_leads(secret: Optional[str] = Query(None)):
    _verify_secret(secret)
    return lead_store.get_all_leads()


@router.get("/stats")
async def pipeline_stats(secret: Optional[str] = Query(None)):
    _verify_secret(secret)
    return get_stats()
