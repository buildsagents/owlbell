from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from leads.pipeline import run_initial_pipeline, run_followup_pipeline
from leads.outreach import get_stats

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

CRON_SECRET = os.getenv("LEADS_CRON_SECRET", "")


def _verify_secret(secret: Optional[str] = None) -> None:
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="LEADS_CRON_SECRET not configured")
    if secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")


@router.post("/run")
async def run_pipeline_endpoint(
    mode: str = Query("initial", description="'initial' or 'followup'"),
    trades: str = Query("hvac,plumbing,roofing,electrical"),
    cities: str = Query("Austin-TX,RoundRock-TX,CedarPark-TX"),
    max_leads: int = Query(80),
    max_outreach: int = Query(80),
    secret: Optional[str] = Query(None),
):
    _verify_secret(secret)

    city_list = []
    for part in cities.split(","):
        part = part.strip()
        if "-" in part:
            city, state = part.rsplit("-", 1)
            city_list.append({"city": city.strip(), "state": state.strip().upper()})

    trade_list = [t.strip() for t in trades.split(",")]

    if mode == "followup":
        result = await run_followup_pipeline(max_daily_outreach=max_outreach)
    else:
        result = await run_initial_pipeline(
            trades=trade_list,
            cities=city_list,
            max_leads=max_leads,
            max_daily_outreach=max_outreach,
        )

    return result


@router.get("/stats")
async def pipeline_stats(secret: Optional[str] = Query(None)):
    _verify_secret(secret)
    return get_stats()
