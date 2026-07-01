from __future__ import annotations

import json
import re
from typing import Any, Optional

import structlog
from openai import AsyncOpenAI

from backend.config import get_settings

logger = structlog.get_logger(__name__)

PERSONALISATION_PROMPT = """You are a sales personalisation specialist. Generate specific, observable observations about this plumbing company's business based on their website and intelligence data.

BUSINESS: {business_name}
INDUSTRY: {industry}
SERVICES: {services}
WEBSITE: {website_url}
WEBSITE_QUALITY: {website_quality}
HAS_EMERGENCY_SERVICE: {has_emergency_service}
HAS_ONLINE_BOOKING: {has_online_booking}
HAS_CONTACT_FORM: {has_contact_form}
PHONE_PROMINENCE: {phone_prominence}
ESTIMATED_CALL_VOLUME: {estimated_call_volume}
WEBSITE_HAS_BLOG: {website_has_blog}
WEBSITE_HAS_TESTIMONIALS: {website_has_testimonials}
WEBSITE_HAS_PRICING: {website_has_pricing}
OBSERVATIONS: {observations}

RULES:
- Every observation must be based on observable information from their website.
- Do NOT invent details. Do NOT say "I noticed" — state facts.
- Each observation should connect to a real plumbing business need Owlbell solves.

Return JSON:
{{
  "observations": [
    {{
      "type": "website_observation",
      "observation": "Factual observation about their website",
      "implication": "What this means for their business",
      "owlbell_relevance": "How Owlbell addresses this"
    }}
  ],
  "hooks": [
    {{
      "type": "hook",
      "hook": "A specific, truthful statement that would grab their attention",
      "evidence": "The observable fact that backs this up",
      "approach": "urgency | growth | efficiency | education"
    }}
  ],
  "personalised_opener": "A 1-sentence opener for an email or call that references a genuine, specific detail about their business"
}}

Aim for 2-3 observations and 2-3 hooks. Return ONLY valid JSON."""

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


class PersonalisationAgent:
    def __init__(self):
        self._client = _get_client()

    async def generate(self, lead: dict[str, Any]) -> list[dict[str, Any]]:
        intel = lead.get("_intelligence", {}) or {}
        opp = lead.get("_opportunity", {}) or {}

        prompt = PERSONALISATION_PROMPT.format(
            business_name=lead.get("name", "Unknown"),
            industry=intel.get("industry", lead.get("trade", "unknown")),
            services=json.dumps(intel.get("services", [])[:5]),
            website_url=lead.get("website", "none"),
            website_quality=intel.get("website_quality", "unknown"),
            has_emergency_service=intel.get("has_emergency_service", False),
            has_online_booking=intel.get("has_online_booking", False),
            has_contact_form=intel.get("has_contact_form", False),
            phone_prominence=intel.get("phone_prominence", "unknown"),
            estimated_call_volume=intel.get("estimated_monthly_call_volume", "unknown"),
            website_has_blog=intel.get("website_has_blog", False),
            website_has_testimonials=intel.get("website_has_testimonials", False),
            website_has_pricing=intel.get("website_has_pricing", False),
            observations=intel.get("observations", "none"),
        )

        if not self._client:
            logger.warning("personalisation.no_llm_client")
            return self._fallback(lead)

        try:
            response = await self._client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=800,
            )
            text = response.choices[0].message.content.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            result = json.loads(text)
            return result
        except Exception as exc:
            logger.error("personalisation.error", error=str(exc))
            return self._fallback(lead)

    def _fallback(self, lead: dict[str, Any]) -> dict[str, Any]:
        intel = lead.get("_intelligence", {}) or {}
        name = lead.get("name", "your business")

        observations = []
        if intel.get("has_emergency_service"):
            observations.append({
                "type": "website_observation",
                "observation": f"{name} offers emergency services with prominent phone display",
                "implication": "Urgent calls must be answered quickly or jobs get lost",
                "owlbell_relevance": "Owlbell answers every call instantly, even after hours",
            })

        hooks = []
        if intel.get("has_emergency_service"):
            hooks.append({
                "type": "hook",
                "hook": "Your emergency plumbing page sells 24/7 service — but who answers those calls at 2 AM?",
                "evidence": "Website displays emergency services with phone number",
                "approach": "urgency",
            })

        return {
            "observations": observations,
            "hooks": hooks,
            "personalised_opener": f"I was looking at {name}'s website — noticed you offer emergency plumbing service and make it easy to call.",
        }

    async def generate_many(
        self,
        leads: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        results = []
        for lead in leads:
            personalisation = await self.generate(lead)
            enriched = {**lead, "_personalisation": personalisation}
            results.append(enriched)
            logger.info("personalisation.generated", name=lead.get("name"))
        return results
