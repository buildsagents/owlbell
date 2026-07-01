from __future__ import annotations

import json
import re
from typing import Any, Optional

import structlog
from openai import AsyncOpenAI

from backend.config import get_settings

logger = structlog.get_logger(__name__)

OUTREACH_PROMPT = """You are a sales copywriter specializing in cold outreach for plumbing companies. Generate multiple email variants for Owlbell (an AI phone receptionist service for plumbers).

BUSINESS: {business_name}
INDUSTRY: {industry}
SERVICES: {services}
WEBSITE: {website_url}
BUSINESS_SIZE: {business_size}
HAS_EMERGENCY_SERVICE: {has_emergency_service}
PHONE_PROMINENCE: {phone_prominence}
ESTIMATED_CALL_VOLUME: {estimated_call_volume}
QUALIFIED: {qualified}
CONFIDENCE: {confidence}
RECOMMENDED_APPROACH: {recommended_approach}
RECOMMENDED_REASON: {recommended_reason}
OBSERVATIONS: {observations}

Generate 3 email variants:

VARIANT 1 — Problem-focused:
Lead with the specific problem they likely face (based on their website data). Reference something specific from their site. Keep it short (100 words).

VARIANT 2 — Curiosity-driven:
Start with an interesting observation or question about their business. Make them wonder. Keep it short (80 words).

VARIANT 3 — Social-proof:
Lead with what similar plumbing companies are doing. Reference their specific service area. Keep it short (100 words).

For each variant include:
- subject_line (max 8 words, no clickbait)
- body (plain text, one paragraph, sign with a random name)
- angle (problem | curiosity | social_proof)

Rules:
- Reference their specific business details (services, location, website)
- Never say "I noticed you missed calls" — focus on the opportunity
- Sound like a real plumbing operator talking to another plumbing operator
- End each variant with: owlbell.xyz/pricing

Return JSON:
{{
  "variants": [
    {{
      "angle": "problem | curiosity | social_proof",
      "subject_line": "...",
      "body": "...",
      "estimated_effectiveness": "low | medium | high"
    }}
  ],
  "recommended_variant": 0|1|2,
  "recommendation_reason": "Why this variant is likely to perform best"
}}

Return ONLY valid JSON."""

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


class OutreachAgent:
    def __init__(self):
        self._client = _get_client()

    async def generate(self, lead: dict[str, Any]) -> dict[str, Any]:
        intel = lead.get("_intelligence", {}) or {}
        opp = lead.get("_opportunity", {}) or {}

        prompt = OUTREACH_PROMPT.format(
            business_name=lead.get("name", "Unknown"),
            industry="plumbing",
            services=json.dumps(intel.get("services", [])[:4]),
            website_url=lead.get("website", "none"),
            business_size=intel.get("business_size_estimate", "unknown"),
            has_emergency_service=intel.get("has_emergency_service", False),
            phone_prominence=intel.get("phone_prominence", "unknown"),
            estimated_call_volume=intel.get("estimated_monthly_call_volume", "unknown"),
            qualified=opp.get("qualified", False),
            confidence=opp.get("confidence", 0),
            recommended_approach=opp.get("recommended_approach", "growth"),
            recommended_reason=opp.get("recommended_reason", ""),
            observations=intel.get("observations", "none"),
        )

        if not self._client:
            logger.warning("outreach.no_llm_client")
            return self._fallback(lead)

        try:
            response = await self._client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000,
            )
            text = response.choices[0].message.content.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            return json.loads(text)
        except Exception as exc:
            logger.error("outreach.error", error=str(exc))
            return self._fallback(lead)

    def _fallback(self, lead: dict[str, Any]) -> dict[str, Any]:
        name = lead.get("name", "your business")
        industry = "plumbing"
        variants = [
            {
                "angle": "problem",
                "subject_line": f"Quick question for {name}",
                "body": f"Hey — I was looking at {name}'s site. You offer plumbing services and your phone number is front and center, which means calls matter to you. But when you're under a sink or on a job, who answers? Missed emergency calls turn into jobs for the next plumber. Owlbell answers every call in your name, books appointments, and texts you the details. owlbell.xyz/pricing — Mike",
                "estimated_effectiveness": "medium",
            },
            {
                "angle": "curiosity",
                "subject_line": f"Your {industry} website",
                "body": f"Quick observation about {name}'s website: you make it easy for customers to call, but there's no mention of what happens when nobody picks up. Plumbing customers with leaks, clogs, or water heater issues usually call the next number. One local plumbing shop picked up 14 extra jobs in the first month after setting this up. owlbell.xyz/pricing — Dave",
                "estimated_effectiveness": "medium",
            },
            {
                "angle": "social_proof",
                "subject_line": "What other plumbers are doing",
                "body": "Hey — quick update on what plumbing companies in your area are doing differently this year. They're adding an AI receptionist that answers every call 24/7, books jobs directly onto their calendar, and texts them the details. One shop recovered $9,800 in missed-call pipeline in a month. owlbell.xyz/pricing — Chris",
                "estimated_effectiveness": "high",
            },
        ]
        return {
            "variants": variants,
            "recommended_variant": 2,
            "recommendation_reason": "Social proof tends to perform best for plumbing companies",
        }

    async def generate_many(
        self,
        leads: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        results = []
        for lead in leads:
            outreach = await self.generate(lead)
            enriched = {**lead, "_outreach": outreach}
            results.append(enriched)
            logger.info("outreach.generated", name=lead.get("name"))
        return results
