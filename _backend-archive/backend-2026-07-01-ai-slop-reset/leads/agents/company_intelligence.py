from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import structlog
from openai import AsyncOpenAI

from backend.config import get_settings

logger = structlog.get_logger(__name__)

EXTRACTION_PROMPT = """You are a business intelligence analyst. Analyze this plumbing company's website and extract structured intelligence.

BUSINESS NAME: {business_name}
WEBSITE URL: {website_url}

WEBSITE CONTENT:
{website_content}

Extract the following fields as JSON. Be thorough — read between the lines. If info isn't available, use null.

{{
  "industry": "plumbing if this is a plumbing company; otherwise other",
  "is_plumbing_company": true|false,
  "services": ["List of specific services offered"],
  "service_area": "Geographic area they serve (city/region)",
  "business_size_estimate": "solo | small_team | medium | large",
  "years_established": "Estimated years in business (number or null)",
  "has_emergency_service": true|false,
  "has_online_booking": true|false,
  "has_contact_form": true|false,
  "phone_prominence": "How prominently is the phone number displayed? none | footer_only | header | click_to_call | sticky",
  "calls_matter": true|false,
  "appointments_matter": true|false,
  "website_quality": "basic | moderate | professional",
  "website_has_blog": true|false,
  "website_has_testimonials": true|false,
  "website_has_pricing": true|false,
  "estimated_monthly_call_volume": "low | medium | high | unknown",
  "ai_fit_score": 0.0-1.0,
  "ai_fit_reasons": ["Specific reasons why AI phone answering would help this plumbing business"],
  "observations": "Notable things about this business relevant to call handling"
}}

Return ONLY valid JSON. No markdown, no explanation."""

MODEL = "llama-3.3-70b-versatile"


def _get_client() -> Optional[AsyncOpenAI]:
    s = get_settings()
    key = s.integrations.groq_api_key
    if not key:
        return None
    if hasattr(key, "get_secret_value"):
        key = key.get_secret_value()
    return AsyncOpenAI(
        api_key=key,
        base_url="https://api.groq.com/openai/v1",
    )


async def _fetch_website(url: str, timeout: int = 15) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) OwlbellIntelligence/1.0",
                "Accept": "text/html,application/xhtml+xml",
            })
        if resp.status_code != 200:
            logger.warning("intel.fetch_failed", url=url, status=resp.status_code)
            return None
        text = resp.text
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = text[:8000]
        return text if len(text) > 100 else None
    except Exception as exc:
        logger.warning("intel.fetch_error", url=url, error=str(exc))
        return None


async def _llm_extract(
    business_name: str,
    website_url: str,
    website_content: str,
) -> Optional[dict[str, Any]]:
    client = _get_client()
    if not client:
        logger.warning("intel.no_llm_client")
        return None

    prompt = EXTRACTION_PROMPT.format(
        business_name=business_name,
        website_url=website_url,
        website_content=website_content[:7000],
    )

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
        )
        text = response.choices[0].message.content.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except Exception as exc:
        logger.error("intel.extract_error", error=str(exc))
        return None


class CompanyIntelligenceAgent:
    def __init__(self):
        self._client = _get_client()

    async def analyze(
        self,
        business_name: str,
        website_url: Optional[str] = None,
    ) -> dict[str, Any]:
        if not website_url:
            return {
                "business_name": business_name,
                "status": "no_website",
                "intelligence": None,
            }

        content = await _fetch_website(website_url)
        if not content:
            return {
                "business_name": business_name,
                "website_url": website_url,
                "status": "unreachable",
                "intelligence": None,
            }

        raw = await _llm_extract(business_name, website_url, content)
        if not raw:
            return {
                "business_name": business_name,
                "website_url": website_url,
                "status": "extraction_failed",
                "intelligence": None,
            }

        return {
            "business_name": business_name,
            "website_url": website_url,
            "status": "complete",
            "intelligence": {
                **raw,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    async def analyze_and_enrich(
        self,
        lead: dict[str, Any],
    ) -> dict[str, Any]:
        result = await self.analyze(
            business_name=lead.get("name", ""),
            website_url=lead.get("website"),
        )
        if result.get("status") == "complete":
            intel = result["intelligence"]
            enriched = {
                **lead,
                "_intelligence": intel,
                "_intel_status": "complete",
                "_intel_extracted_at": intel.get("extracted_at"),
                "industry": intel.get("industry", lead.get("trade")),
                "ai_fit_score": intel.get("ai_fit_score"),
                "has_emergency_service": intel.get("has_emergency_service"),
                "has_online_booking": intel.get("has_online_booking"),
                "phone_prominence": intel.get("phone_prominence"),
                "estimated_call_volume": intel.get("estimated_monthly_call_volume"),
                "website_quality": intel.get("website_quality"),
                "business_size": intel.get("business_size_estimate"),
                "services": intel.get("services"),
            }
            return enriched
        return {**lead, "_intel_status": result["status"]}

    async def analyze_many(
        self,
        leads: list[dict[str, Any]],
        max_concurrent: int = 5,
    ) -> list[dict[str, Any]]:
        results = []
        for i, lead in enumerate(leads):
            if i >= max_concurrent:
                break
            enriched = await self.analyze_and_enrich(lead)
            results.append(enriched)
            logger.info("intel.lead_complete",
                name=lead.get("name"),
                status=enriched.get("_intel_status"),
                idx=i + 1,
                total=min(len(leads), max_concurrent))
        return results
