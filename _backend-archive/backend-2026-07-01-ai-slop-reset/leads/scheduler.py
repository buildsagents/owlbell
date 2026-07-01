"""In-process async scheduler for the outreach pipeline.

Runs pipeline tasks on configurable intervals using asyncio background tasks.
Wired into the FastAPI lifespan — starts on boot, cancels on shutdown.

Schedule:
  - Full pipeline (score → initial → followups → pool refill): every 24h
  - Reply check + AI response: every 2h
  - Pool health check: every 6h
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import structlog

from backend.config import get_settings

logger = structlog.get_logger(__name__)

_PIPELINE_INTERVAL = 24 * 60 * 60  # 24h
_REPLY_INTERVAL = 2 * 60 * 60      # 2h
_POOL_INTERVAL = 6 * 60 * 60       # 6h


async def _run_pipeline() -> None:
    """Execute the full outreach pipeline."""
    try:
        from backend.leads.outreach import run_full_pipeline
        result = await run_full_pipeline(max_initial=15, max_followups=20)
        logger.info("scheduler.pipeline.complete", sent=result.get("initial", {}).get("sent", 0))
    except Exception as exc:
        logger.error("scheduler.pipeline.error", error=str(exc))


async def _check_replies() -> None:
    """Check inbox for replies and auto-respond."""
    try:
        from backend.leads.reply_handler import handle_replies
        result = await handle_replies()
        logger.info("scheduler.replies.complete", handled=result.get("replied", 0))
    except Exception as exc:
        logger.error("scheduler.replies.error", error=str(exc))


async def _check_pool() -> None:
    """Ensure lead pool has enough entries."""
    try:
        from backend.leads.lead_generator import ensure_lead_pool, get_pool_depth
        await ensure_lead_pool(min_pool=30)
        depth = get_pool_depth()
        logger.info("scheduler.pool.complete", depth=depth)
    except Exception as exc:
        logger.error("scheduler.pool.error", error=str(exc))


async def _pipeline_loop() -> None:
    """Background loop: run full pipeline every 24h."""
    await asyncio.sleep(60)  # stagger: pipeline runs after 1m
    while True:
        logger.info("scheduler.pipeline.starting")
        await _run_pipeline()
        await asyncio.sleep(_PIPELINE_INTERVAL)


async def _reply_loop() -> None:
    """Background loop: check replies every 2h."""
    await asyncio.sleep(120)  # stagger: replies after 2m
    while True:
        logger.info("scheduler.replies.starting")
        await _check_replies()
        await asyncio.sleep(_REPLY_INTERVAL)


async def _pool_loop() -> None:
    """Background loop: check pool health every 6h."""
    await asyncio.sleep(300)  # stagger: pool after 5m
    while True:
        logger.info("scheduler.pool.starting")
        await _check_pool()
        await asyncio.sleep(_POOL_INTERVAL)


async def start_scheduler(app) -> list[asyncio.Task]:
    """Launch all background scheduler tasks.

    Returns a list of tasks for the caller to cancel on shutdown.
    Tasks are only started when the leads feature is configured.
    """
    secret = os.getenv("LEADS_CRON_SECRET", "")

    if not secret:
        logger.info("scheduler.skipped.no_secret")
        return []

    logger.info("scheduler.starting")
    tasks = [
        asyncio.create_task(_pipeline_loop(), name="scheduler-pipeline"),
        asyncio.create_task(_reply_loop(), name="scheduler-replies"),
        asyncio.create_task(_pool_loop(), name="scheduler-pool"),
    ]
    logger.info("scheduler.started", task_count=len(tasks))
    return tasks
