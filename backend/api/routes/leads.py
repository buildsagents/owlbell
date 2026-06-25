from __future__ import annotations

import asyncio
import os
import threading
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.leads.scraper import find_contractors
from backend.leads.email_finder import find_emails_for_leads
from backend.leads.outreach import send_initial_outreach, send_followups, get_stats
from backend.leads import lead_store

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

CRON_SECRET = os.getenv("LEADS_CRON_SECRET", "")
RUNNING = threading.Event()  # prevents overlapping runs
_last_run: dict = {}


def _verify_secret(secret: Optional[str] = None) -> None:
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="LEADS_CRON_SECRET not configured")
    if secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")


def _run_pipeline_sync(
    mode: str,
    trades: list[str],
    cities: list[dict],
    max_leads: int,
    max_outreach: int,
) -> dict[str, Any]:
    """Synchronous pipeline runner for background thread — no asyncio needed."""
    import asyncio
    import time as _time

    asyncio.run(_run_async(mode, trades, cities, max_leads, max_outreach))
    return _last_run.get("result", {"status": "unknown"})


async def _run_async(
    mode: str,
    trades: list[str],
    cities: list[dict],
    max_leads: int,
    max_outreach: int,
) -> dict[str, Any]:
    from leads.pipeline import run_initial_pipeline, run_followup_pipeline

    if mode == "followup":
        return await run_followup_pipeline(max_daily_outreach=max_outreach)
    return await run_initial_pipeline(
        trades=trades,
        cities=cities,
        max_leads=max_leads,
        max_daily_outreach=max_outreach,
    )


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

    if RUNNING.is_set():
        return {"status": "already_running", "mode": mode}

    RUNNING.set()

    async def _bg():
        global _last_run
        try:
            result = await _run_async(mode, trade_list, city_list, max_leads, max_outreach)
            _last_run = {"status": "done", "result": result, "ts": time.time()}
        except Exception as exc:
            _last_run = {"status": "error", "error": str(exc), "ts": time.time()}
        finally:
            RUNNING.clear()

    t = threading.Thread(target=lambda: asyncio.run(_bg()), daemon=True)
    t.start()

    return {
        "status": "accepted",
        "mode": mode,
        "message": "Pipeline started in background. See /api/v1/leads/last-run and /api/v1/leads/stats for progress.",
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
    return get_stats()
