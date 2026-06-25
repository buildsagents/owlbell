from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import structlog

from backend.leads.scraper import find_contractors, is_configured as scraper_configured
from backend.leads.email_finder import find_emails_for_leads
from backend.leads.outreach import (
    send_initial_outreach,
    send_followups,
    get_stats as outreach_stats,
)
from backend.leads import lead_store

logger = structlog.get_logger(__name__)


class LeadPipeline:
    async def run(
        self,
        mode: str = "initial",
        trades: Optional[list[str]] = None,
        cities: Optional[list[dict[str, str]]] = None,
        max_leads: int = 50,
        max_daily_outreach: int = 80,
        output_file: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if mode == "followup":
            return await run_followup_pipeline(
                max_daily_outreach=max_daily_outreach,
                output_file=output_file,
                dry_run=dry_run,
            )
        return await run_initial_pipeline(
            trades=trades,
            cities=cities,
            max_leads=max_leads,
            max_daily_outreach=max_daily_outreach,
            output_file=output_file,
            dry_run=dry_run,
        )


async def run_initial_pipeline(
    trades: Optional[list[str]] = None,
    cities: Optional[list[dict[str, str]]] = None,
    max_leads: int = 50,
    max_daily_outreach: int = 80,
    output_file: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    start = time.time()
    logger.info("pipeline.initial_starting", trades=trades, cities=cities, dry_run=dry_run)

    if not scraper_configured():
        logger.warning("pipeline.scraper_not_configured")
        return {"status": "error", "error": "Google Maps API key not configured"}

    leads = await find_contractors(trades=trades, cities=cities, max_per_search=min(max_leads, 20))
    logger.info("pipeline.scrape_complete", count=len(leads))

    if not leads:
        return {"status": "error", "error": "No leads found"}

    if output_file:
        raw_path = Path(output_file).with_suffix(".raw.json")
        raw_path.write_text(json.dumps(leads, indent=2, default=str))

    leads_with_emails = await find_emails_for_leads(leads)
    with_email = [l for l in leads_with_emails if l.get("email")]
    without_email = [l for l in leads_with_emails if not l.get("email")]

    logger.info("pipeline.email_find_complete",
        total=len(leads_with_emails),
        with_email=len(with_email),
        without_email=len(without_email))

    outreach_results = await send_initial_outreach(leads_with_emails, max_per_day=max_daily_outreach, dry_run=dry_run)
    outreach_sent = [l for l in outreach_results if l.get("outreach_status") == "sent"]

    elapsed = time.time() - start
    logger.info("pipeline.initial_complete",
        elapsed_s=round(elapsed, 1),
        leads_found=len(leads),
        with_email=len(with_email),
        emails_sent=len(outreach_sent),
        dry_run=dry_run)

    if output_file:
        out_path = Path(output_file)
        out_path.write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "initial",
            "dry_run": dry_run,
            "summary": {
                "elapsed_s": round(elapsed, 1),
                "leads_found": len(leads),
                "with_email": len(with_email),
                "without_email": len(without_email),
                "emails_sent": len(outreach_sent),
                "email_daily_cap": max_daily_outreach,
            },
            "sent": [{"name": l.get("name"), "email": l.get("email")} for l in outreach_results if l.get("outreach_status") == "sent"],
            "skipped": [{"name": l.get("name"), "status": l.get("outreach_status")} for l in outreach_results if l.get("outreach_status") != "sent"],
        }, indent=2, default=str))

    return {
        "status": "ok",
        "mode": "initial",
        "elapsed_s": round(elapsed, 1),
        "leads_found": len(leads),
        "with_email": len(with_email),
        "without_email": len(without_email),
        "emails_sent": len(outreach_sent),
    }


async def run_followup_pipeline(
    max_daily_outreach: int = 80,
    output_file: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    start = time.time()
    logger.info("pipeline.followup_starting", dry_run=dry_run)

    results = await send_followups(max_per_day=max_daily_outreach, dry_run=dry_run)

    elapsed = time.time() - start
    logger.info("pipeline.followup_complete",
        elapsed_s=round(elapsed, 1),
        followups_sent=len(results),
        dry_run=dry_run)

    if output_file:
        out_path = Path(output_file)
        out_path.write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": "followup",
            "dry_run": dry_run,
            "summary": {
                "elapsed_s": round(elapsed, 1),
                "followups_sent": len(results),
            },
            "sent": [{"name": l.get("name"), "email": l.get("email"), "stage": l.get("outreach_status")} for l in results],
        }, indent=2, default=str))

    return {
        "status": "ok",
        "mode": "followup",
        "elapsed_s": round(elapsed, 1),
        "followups_sent": len(results),
    }
