"""operations/billing/routes.py - Usage metering read API.

Exposes the DB-backed usage metering for the authenticated tenant:
    GET /usage/summary    -> headline counters for a period
    GET /usage/breakdown  -> per-action-type breakdown
    GET /usage/events     -> recent raw usage records
    GET /usage/snapshot   -> computed usage snapshot for a period

All endpoints are scoped to the caller's tenant (from the JWT). Writes happen
on the call lifecycle (see ``UsageTracker`` / ``on_call_ended``), so this
router is read-only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Query

from api.dependencies import CurrentUser

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/usage", tags=["Operations — Usage"])


@router.get("/summary")
async def usage_summary(
    period: Optional[str] = Query(None, description="YYYY-MM; defaults to current month"),
    user=CurrentUser,
) -> dict[str, Any]:
    """Headline usage counters (calls, minutes, tokens, API requests)."""
    from backend.dependencies import get_usage_tracker

    tracker = await get_usage_tracker()
    data = await tracker.get_usage_summary(user.tenant_id, period)
    return {"success": True, "data": data}


@router.get("/breakdown")
async def usage_breakdown(
    period: Optional[str] = Query(None, description="YYYY-MM; defaults to current month"),
    user=CurrentUser,
) -> dict[str, Any]:
    """Usage broken down by action type for a period."""
    from backend.dependencies import get_usage_tracker

    tracker = await get_usage_tracker()
    data = await tracker.get_usage_breakdown(user.tenant_id, period)
    return {"success": True, "data": data}


@router.get("/events")
async def usage_events(
    limit: int = Query(100, ge=1, le=500),
    user=CurrentUser,
) -> dict[str, Any]:
    """Most recent raw usage records for the tenant."""
    from backend.dependencies import get_usage_tracker

    tracker = await get_usage_tracker()
    events = await tracker.get_recent_events(user.tenant_id, limit=limit)
    return {"success": True, "data": events}


@router.get("/snapshot")
async def usage_snapshot(
    period: Optional[str] = Query(None, description="YYYY-MM; defaults to current month"),
    user=CurrentUser,
) -> dict[str, Any]:
    """Computed usage snapshot (totals by resource) for a period."""
    from backend.dependencies import get_usage_tracker

    tracker = await get_usage_tracker()
    period = period or datetime.utcnow().strftime("%Y-%m")
    snapshot = await tracker.compute_snapshot(user.tenant_id, period)
    return {"success": True, "data": snapshot.to_dict()}
