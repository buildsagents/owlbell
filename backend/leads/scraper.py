"""
leads/scraper.py - Contractor lead finder via Google Places API.

Uses the Google Places API Text Search + Place Details to find
contractors by trade and city. Returns structured lead data.

Requires env var: INTEGRATION_GOOGLE_MAPS_API_KEY
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional
import httpx
import structlog

from backend.config import get_settings

logger = structlog.get_logger(__name__)

PLACES_API_BASE = "https://maps.googleapis.com/maps/api/place"

TRADE_KEYWORDS = {
    "hvac": "HVAC contractor",
    "plumbing": "plumber",
    "electrical": "electrician",
    "roofing": "roofer",
    "landscaping": "landscaper",
    "painting": "painter",
    "pest_control": "pest control",
    "flooring": "flooring contractor",
    "gutters": "gutter contractor",
    "general": "general contractor",
}


def _api_key() -> Optional[str]:
    """Get the Google Maps API key from settings."""
    s = get_settings()
    if hasattr(s.integrations, 'google_maps_api_key') and s.integrations.google_maps_api_key:
        key = s.integrations.google_maps_api_key
        if hasattr(key, 'get_secret_value'):
            return key.get_secret_value()
        return str(key)
    import os
    return os.getenv("INTEGRATION_GOOGLE_MAPS_API_KEY")


def is_configured() -> bool:
    return bool(_api_key())


async def text_search(trade: str, city: str, state: str, max_results: int = 20) -> list[dict[str, Any]]:
    """Search Google Places for contractors by trade + location.

    Returns raw place results with basic info.
    """
    key = _api_key()
    if not key:
        logger.warning("google_maps.not_configured")
        return []

    keyword = TRADE_KEYWORDS.get(trade, trade)
    query = f"{keyword} in {city}, {state}"

    url = f"{PLACES_API_BASE}/textsearch/json"
    params = {
        "query": query,
        "key": key,
        "radius": 50000,
    }

    all_results = []
    next_page_token = None

    for _ in range(3):
        if next_page_token:
            params["pagetoken"] = next_page_token
            time.sleep(2)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params)

            if resp.status_code != 200:
                logger.warning("places_api.error", status=resp.status_code, body=resp.text[:200])
                break

            data = resp.json()
            if data.get("status") != "OK":
                if data.get("status") == "ZERO_RESULTS":
                    break
                logger.warning("places_api.status", status=data.get("status"), error=data.get("error_message"))
                break

            results = data.get("results", [])
            all_results.extend(results)

            if len(all_results) >= max_results:
                all_results = all_results[:max_results]
                break

            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break
        except Exception as exc:
            logger.error("places_api.error", error=str(exc))
            break

    return all_results


async def get_place_details(place_id: str) -> Optional[dict[str, Any]]:
    """Get full details for a place including phone number."""
    key = _api_key()
    if not key:
        return None

    url = f"{PLACES_API_BASE}/details/json"
    params = {
        "place_id": place_id,
        "key": key,
        "fields": "name,formatted_phone_number,international_phone_number,website,formatted_address,rating,user_ratings_total,business_status,opening_hours",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)

        if resp.status_code != 200:
            return None

        data = resp.json()
        if data.get("status") != "OK":
            return None

        return data.get("result")
    except Exception as exc:
        logger.error("places_api.details_error", place_id=place_id, error=str(exc))
        return None


def parse_contractor(place: dict[str, Any], details: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Parse a place result into a standardized lead record."""
    info = details or place

    return {
        "name": info.get("name", ""),
        "phone": info.get("formatted_phone_number") or info.get("international_phone_number", ""),
        "address": info.get("formatted_address", ""),
        "website": info.get("website", ""),
        "rating": info.get("rating"),
        "review_count": info.get("user_ratings_total", 0),
        "place_id": place.get("place_id", ""),
        "business_status": info.get("business_status", ""),
        "source": "google_places",
    }


async def find_contractors(
    trades: Optional[list[str]] = None,
    cities: Optional[list[dict[str, str]]] = None,
    max_per_search: int = 20,
) -> list[dict[str, Any]]:
    """Find contractors across multiple trades and cities.

    Args:
        trades: List of trade keys (e.g. ["hvac", "plumbing"]). Defaults to all.
        cities: List of {"city": str, "state": str}. Defaults to a few TX cities.
        max_per_search: Max results per trade/city combo.

    Returns:
        List of contractor lead records.
    """
    if not is_configured():
        logger.warning("leads.scraper.not_configured")
        return []

    if not trades:
        trades = list(TRADE_KEYWORDS.keys())[:3]

    if not cities:
        cities = [
            {"city": "Austin", "state": "TX"},
            {"city": "Round Rock", "state": "TX"},
            {"city": "Cedar Park", "state": "TX"},
        ]

    all_leads = []
    seen_phones = set()

    for trade in trades:
        for loc in cities:
            results = await text_search(trade, loc["city"], loc["state"], max_results=max_per_search)

            for place in results:
                phone = place.get("formatted_phone_number", "")
                if phone and phone in seen_phones:
                    continue
                if phone:
                    seen_phones.add(phone)

                details = None
                if place.get("place_id"):
                    details = await get_place_details(place["place_id"])
                    time.sleep(0.1)

                lead = parse_contractor(place, details)

                if lead["phone"]:
                    all_leads.append(lead)

            logger.info("leads.scraped", trade=trade, city=loc["city"], count=len(results), leads_with_phone=len(all_leads))

    return all_leads
