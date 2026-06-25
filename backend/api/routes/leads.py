from __future__ import annotations

import os
import threading
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

CRON_SECRET = os.getenv("LEADS_CRON_SECRET", "")
_last_run: dict = {}  # tracks status/result of background runs


def _verify_secret(secret: Optional[str] = None) -> None:
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="LEADS_CRON_SECRET not configured")
    if secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")


def _run_in_background(
    mode: str,
    trades: list[str],
    cities: list[dict],
    max_leads: int,
    max_outreach: int,
) -> None:
    """Run pipeline in a background thread so Railway nginx doesn't timeout."""
    import asyncio
    from leads.pipeline import run_initial_pipeline, run_followup_pipeline

    async def _run():
        global _last_run
        try:
            if mode == "followup":
                result = await run_followup_pipeline(max_daily_outreach=max_outreach)
            else:
                result = await run_initial_pipeline(
                    trades=trades,
                    cities=cities,
                    max_leads=max_leads,
                    max_daily_outreach=max_outreach,
                )
            _last_run = {"status": "done", "result": result, "ts": time.time()}
        except Exception as exc:
            _last_run = {"status": "error", "error": str(exc), "ts": time.time()}

    asyncio.run(_run())


@router.post("/run")
async def run_pipeline_endpoint(
    mode: str = Query("initial", description="'initial' or 'followup'"),
    trades: str = Query("hvac,plumbing,roofing,electrical"),
    cities: str = Query("Austin-TX,RoundRock-TX,CedarPark-TX"),
    max_leads: int = Query(80),
    max_outreach: int = Query(80),
    secret: Optional[str] = Query(None),
    sync: bool = Query(False, description="Run synchronously (may timeout on Railway)"),
):
    _verify_secret(secret)

    city_list = []
    for part in cities.split(","):
        part = part.strip()
        if "-" in part:
            city, state = part.rsplit("-", 1)
            city_list.append({"city": city.strip(), "state": state.strip().upper()})

    trade_list = [t.strip() for t in trades.split(",")]

    if sync:
        from leads.pipeline import run_initial_pipeline, run_followup_pipeline

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

    t = threading.Thread(
        target=_run_in_background,
        args=(mode, trade_list, city_list, max_leads, max_outreach),
        daemon=True,
    )
    t.start()
    return {
        "status": "accepted",
        "mode": mode,
        "message": "Pipeline started in background. Check /api/v1/leads/stats and /api/v1/leads/last-run for progress.",
    }


@router.get("/last-run")
async def last_run(secret: Optional[str] = Query(None)):
    _verify_secret(secret)
    if not _last_run:
        return {"status": "no_runs_yet"}
    return _last_run


@router.get("/stats")
async def pipeline_stats(secret: Optional[str] = Query(None)):
    _verify_secret(secret)
    from leads.outreach import get_stats
    return get_stats()
