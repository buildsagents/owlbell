"""Auto-discovers new markets when lead pool runs low — never run out of leads."""

from __future__ import annotations

import random
from typing import Any, Optional

import structlog

from backend.leads import lead_store
from backend.leads.scraper import find_contractors, is_configured as scraper_configured
from backend.leads.email_finder import find_emails_for_leads

logger = structlog.get_logger(__name__)

# ── Market discovery queue ─────────────────────────────────────

ALL_TRADES = ["plumbing"]

# Major metro areas across the US — stage 1
MAJOR_METROS = [
    {"city": "Austin", "state": "TX"},
    {"city": "Round Rock", "state": "TX"},
    {"city": "Cedar Park", "state": "TX"},
    {"city": "Dallas", "state": "TX"},
    {"city": "Fort Worth", "state": "TX"},
    {"city": "Houston", "state": "TX"},
    {"city": "San Antonio", "state": "TX"},
    {"city": "Phoenix", "state": "AZ"},
    {"city": "Mesa", "state": "AZ"},
    {"city": "Denver", "state": "CO"},
    {"city": "Colorado Springs", "state": "CO"},
    {"city": "Atlanta", "state": "GA"},
    {"city": "Charlotte", "state": "NC"},
    {"city": "Raleigh", "state": "NC"},
    {"city": "Nashville", "state": "TN"},
    {"city": "Orlando", "state": "FL"},
    {"city": "Tampa", "state": "FL"},
    {"city": "Jacksonville", "state": "FL"},
    {"city": "Las Vegas", "state": "NV"},
    {"city": "Portland", "state": "OR"},
    {"city": "Seattle", "state": "WA"},
]

# Stage 2 — suburbs and secondary markets
SECONDARY_MARKETS = [
    {"city": "Georgetown", "state": "TX"},
    {"city": "Pflugerville", "state": "TX"},
    {"city": "Kyle", "state": "TX"},
    {"city": "Buda", "state": "TX"},
    {"city": "San Marcos", "state": "TX"},
    {"city": "Frisco", "state": "TX"},
    {"city": "Plano", "state": "TX"},
    {"city": "Irving", "state": "TX"},
    {"city": "Arlington", "state": "TX"},
    {"city": "Garland", "state": "TX"},
    {"city": "Mesquite", "state": "TX"},
    {"city": "Carrollton", "state": "TX"},
    {"city": "The Woodlands", "state": "TX"},
    {"city": "Sugar Land", "state": "TX"},
    {"city": "Katy", "state": "TX"},
    {"city": "Scottsdale", "state": "AZ"},
    {"city": "Tempe", "state": "AZ"},
    {"city": "Chandler", "state": "AZ"},
    {"city": "Gilbert", "state": "AZ"},
    {"city": "Glendale", "state": "AZ"},
    {"city": "Aurora", "state": "CO"},
    {"city": "Lakewood", "state": "CO"},
    {"city": "Sandy Springs", "state": "GA"},
    {"city": "Roswell", "state": "GA"},
    {"city": "Marietta", "state": "GA"},
]


def _get_discovery_queue() -> list[dict[str, Any]]:
    """Get or initialize the market discovery queue in lead store."""
    return lead_store.get_discovery_queue()


def _save_discovery_queue(queue: list[dict[str, Any]]) -> None:
    lead_store.set_discovery_queue(queue)


def _init_discovery_queue() -> list[dict[str, Any]]:
    """Build initial discovery queue if empty."""
    existing = _get_discovery_queue()
    if existing:
        return existing

    queue = []
    for city in MAJOR_METROS:
        for trade in ALL_TRADES:
            queue.append({"city": city["city"], "state": city["state"], "trade": trade, "stage": 1})
    random.shuffle(queue)
    _save_discovery_queue(queue)
    return queue


def _expand_to_secondary(queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """When stage 1 is exhausted, add secondary markets."""
    for city in SECONDARY_MARKETS:
        for trade in ALL_TRADES:
            queue.append({"city": city["city"], "state": city["state"], "trade": trade, "stage": 2})
    random.shuffle(queue)
    return queue


# ── Lead pool health ──────────────────────────────────────────


def get_pool_depth() -> int:
    """How many leads are available to send to right now."""
    pending = lead_store.get_pending_send(limit=9999)
    return len(pending)


def is_pool_low(threshold: int = 30) -> bool:
    """Check if we're running low on leads to send."""
    return get_pool_depth() < threshold


def get_empty_staging() -> list[dict[str, Any]]:
    """Get leads that have no email — these need email finding."""
    all_leads = lead_store.get_all_leads()
    return [l for l in all_leads if not l.get("email") and l.get("website") and l["status"] == "new"]


# ── Auto-refill ───────────────────────────────────────────────


async def discover_new_leads(
    trades: Optional[list[str]] = None,
    max_per_search: int = 10,
) -> int:
    """Pull next market from the discovery queue and scrape leads."""
    if not scraper_configured():
        logger.warning("generator.scraper_not_configured")
        return 0

    queue = _get_discovery_queue()
    if not queue:
        queue = _init_discovery_queue()

    # Pop up to 3 markets from queue
    markets = []
    while len(markets) < 3 and queue:
        markets.append(queue.pop(0))

    if not markets:
        # Expand to secondary markets
        queue = _expand_to_secondary(queue)
        if not queue:
            logger.info("generator.all_markets_exhausted")
            return 0
        while len(markets) < 3 and queue:
            markets.append(queue.pop(0))

    _save_discovery_queue(queue)

    active_trades = trades or ALL_TRADES
    total_added = 0

    for market in markets:
        trade_list = [market.get("trade", t) for t in [market.get("trade")] if market.get("trade")] or active_trades

        leads = await find_contractors(
            trades=trade_list,
            cities=[{"city": market["city"], "state": market["state"]}],
            max_per_search=max_per_search,
        )

        if not leads:
            logger.info("generator.no_leads_found", market=market)
            continue

        # Find emails for leads that have websites
        leads_with_emails = await find_emails_for_leads(leads)

        # Add to store (dedup happens inside add_lead)
        added = 0
        for lead in leads_with_emails:
            stored = lead_store.add_lead(lead)
            if stored.get("_new", True):
                added += 1

        total_added += added
        logger.info("generator.market_scraped", market=market, leads=len(leads), new=added)

    logger.info("generator.discovery_complete", markets=len(markets), new_leads=total_added)
    return total_added


async def ensure_lead_pool(min_pool: int = 50) -> dict[str, Any]:
    """Ensure we have enough leads — auto-refill if low."""
    depth = get_pool_depth()
    result = {"pool_depth": depth, "refilled": 0, "needs_refill": False}

    if depth >= min_pool:
        return result

    if not scraper_configured():
        logger.warning("generator.cannot_refill_scraper_not_configured")
        return result

    logger.info("generator.refilling", current_depth=depth, target=min_pool)
    new_leads = await discover_new_leads(max_per_search=10)
    result["refilled"] = new_leads
    result["needs_refill"] = True
    result["new_depth"] = get_pool_depth()

    return result


async def discover_untapped_markets() -> list[dict[str, Any]]:
    """Identify which markets we haven't scraped yet."""
    queue = _get_discovery_queue()
    if not queue:
        queue = _init_discovery_queue()

    return queue[:10]
