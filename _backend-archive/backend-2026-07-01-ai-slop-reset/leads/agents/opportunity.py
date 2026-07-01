from __future__ import annotations

import json
import re
from typing import Any, Optional

import structlog
from openai import AsyncOpenAI

from backend.config import get_settings

logger = structlog.get_logger(__name__)

OPPORTUNITY_PROMPT = """You are a sales qualification analyst. Determine whether this plumbing company is worth reaching out to for Owlbell (an AI phone receptionist service for plumbers).

BUSINESS: {business_name}
INDUSTRY: {industry}
SERVICES: {services}
WEBSITE: {website_url}
WEBSITE_QUALITY: {website_quality}
HAS_EMERGENCY_SERVICE: {has_emergency_service}
HAS_ONLINE_BOOKING: {has_online_booking}
PHONE_PROMINENCE: {phone_prominence}
ESTIMATED_CALL_VOLUME: {estimated_call_volume}
BUSINESS_SIZE: {business_size}
AI_FIT_SCORE: {ai_fit_score}
MISSED_CALL_RISK: {missed_call_risk}
BUYING_TRIGGERS: {buying_triggers}
OBSERVATIONS: {observations}

Analyze:
0. Is this actually a plumbing company? If not, mark qualified=false.
1. Does this business rely on inbound phone calls?
2. Would missed calls cost them real money? (Weigh MISSED_CALL_RISK and BUYING_TRIGGERS heavily — these come from real Google reviews and published hours.)
3. Is there a clear trigger (emergency services, appointment booking, review complaints about responsiveness)?
4. Are they big enough to afford the plumbing receptionist offer?
5. Do they appear to be growth-oriented?

Return JSON:
{{
  "qualified": true|false,
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of qualification decision",
  "estimated_missed_call_cost_per_month": "dollar amount or null",
  "recommended_approach": "urgency | growth | efficiency | education",
  "recommended_reason": "Why this angle would work best",
  "red_flags": ["Any reasons not to pursue"],
  "green_flags": ["Reasons this is a good fit"]
}}

Return ONLY valid JSON. No markdown."""

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


class OpportunityAgent:
    def __init__(self):
        self._client = _get_client()

    async def evaluate(self, lead: dict[str, Any]) -> dict[str, Any]:
        intel = lead.get("_intelligence", {}) or {}
        signals = lead.get("_signals", {}) or {}

        triggers = signals.get("triggers") or []
        prompt = OPPORTUNITY_PROMPT.format(
            business_name=lead.get("name", "Unknown"),
            industry=intel.get("industry", lead.get("trade", "unknown")),
            services=json.dumps(intel.get("services", [])),
            website_url=lead.get("website", "none"),
            website_quality=intel.get("website_quality", "unknown"),
            has_emergency_service=intel.get("has_emergency_service", False),
            has_online_booking=intel.get("has_online_booking", False),
            phone_prominence=intel.get("phone_prominence", "unknown"),
            estimated_call_volume=intel.get("estimated_monthly_call_volume", "unknown"),
            business_size=intel.get("business_size_estimate", "unknown"),
            ai_fit_score=intel.get("ai_fit_score", "unknown"),
            missed_call_risk=signals.get("missed_call_risk", "unknown"),
            buying_triggers="; ".join(triggers) if triggers else "none detected",
            observations=intel.get("observations", "none"),
        )

        if not self._client:
            logger.warning("opportunity.no_llm_client")
            return self._heuristic(lead)

        try:
            response = await self._client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=600,
            )
            text = response.choices[0].message.content.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            result = json.loads(text)
            return {
                **result,
                "_qualified_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
            }
        except Exception as exc:
            logger.error("opportunity.eval_error", error=str(exc))
            return self._heuristic(lead)

    def _heuristic(self, lead: dict[str, Any]) -> dict[str, Any]:
        intel = lead.get("_intelligence", {}) or {}
        signals = lead.get("_signals", {}) or {}
        score = intel.get("ai_fit_score", 0.5)

        if score is None:
            score = 0.5

        green = []
        red = []

        industry = (intel.get("industry") or lead.get("trade") or "").lower()
        if industry and "plumb" not in industry:
            red.append("Not a plumbing company")
            return {
                "qualified": False,
                "confidence": 0.1,
                "reasoning": "Out of scope for the current plumbing-only campaign",
                "estimated_missed_call_cost_per_month": None,
                "recommended_approach": "education",
                "recommended_reason": "Only plumbing companies are in scope",
                "green_flags": green,
                "red_flags": red,
                "_qualified_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
            }

        # Observable buying triggers are the strongest evidence — weight them.
        for trigger in signals.get("triggers", []):
            green.append(trigger)
        missed_call_risk = signals.get("missed_call_risk") or 0.0
        if missed_call_risk >= 0.4:
            # Real review complaints about responsiveness dominate the score.
            score = max(score, 0.5 + missed_call_risk * 0.4)

        if intel.get("has_emergency_service"):
            green.append("Emergency services — missed calls lose urgent jobs")
        if intel.get("phone_prominence") in ("header", "click_to_call", "sticky"):
            green.append("Phone is primary contact method")
        if intel.get("estimated_monthly_call_volume") == "high":
            green.append("High call volume — high missed-call risk")
        if intel.get("has_online_booking"):
            green.append("Already has online booking — understands digital tools")

        if intel.get("website_quality") == "basic":
            red.append("Basic website — may not be tech-forward")
        if score and score < 0.3:
            red.append("Low AI fit score")

        # A fresh, evidence-backed trigger qualifies the lead on its own.
        qualified = bool(signals.get("has_fresh_trigger")) or (score >= 0.4 if score else False)

        # Lead with the angle the evidence supports.
        approach = "urgency" if missed_call_risk >= 0.4 or signals.get("after_hours_gap") else "growth"

        return {
            "qualified": qualified,
            "confidence": round(min(score, 1.0), 3) if score else 0.5,
            "reasoning": "Heuristic qualification based on review signals and intelligence",
            "estimated_missed_call_cost_per_month": None,
            "recommended_approach": approach,
            "recommended_reason": (
                "Review evidence of missed/slow calls" if approach == "urgency"
                else "AI reception improves operations"
            ),
            "green_flags": green,
            "red_flags": red,
            "_qualified_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }

    async def evaluate_many(
        self,
        leads: list[dict[str, Any]],
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        results = []
        for lead in leads:
            eval_result = await self.evaluate(lead)
            enriched = {
                **lead,
                "_opportunity": eval_result,
                "_opportunity_qualified": eval_result.get("qualified", False),
                "_opportunity_confidence": eval_result.get("confidence", 0),
                "_opportunity_approach": eval_result.get("recommended_approach"),
            }
            results.append(enriched)
            logger.info("opportunity.evaluated",
                name=lead.get("name"),
                qualified=enriched["_opportunity_qualified"],
                confidence=enriched["_opportunity_confidence"])
        return results
