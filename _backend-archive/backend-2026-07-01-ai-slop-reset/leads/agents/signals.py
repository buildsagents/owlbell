"""Signal Detection Agent.

Owlbell's edge is *signals*, not lists. This agent turns raw lead data
(Google reviews, opening hours, company intelligence) into observable
*triggers* — concrete, fresh reasons a business is likely to benefit from an
AI receptionist *right now*.

The single strongest signal is review text that mentions missed calls,
voicemail, or slow responsiveness. Google Places returns up to 5 reviews per
business; we mine that text deterministically (keyword categories) so this
works at $0 with no LLM, and is fully testable. An optional LLM refinement
exists for nuance but is never required.

Every trigger emitted here is backed by an observable fact (a real review
quote, a published-hours gap, a missing booking widget) so downstream
Personalisation/Outreach can reference it truthfully — never invented.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


# ── Responsiveness-complaint detection ────────────────────────────
# Categories of review phrasing that indicate calls are being missed.
# Patterns are matched case-insensitively against review text.

_REVIEW_PATTERNS: dict[str, list[str]] = {
    "voicemail": [
        r"voice ?mail",
        r"goes? to (?:the )?machine",
    ],
    "no_answer": [
        r"no(?:body| one)? (?:ever )?(?:answer|pick(?:ed|s)? up)",
        r"(?:didn'?t|did not|doesn'?t|does not|never|won'?t|will not|wouldn'?t|would not) answer",
        r"phone just rings",
        r"rings? and rings?",
        r"(?:couldn'?t|could not|can'?t|cannot|can not) (?:get|reach|get a hold of|get hold of)",
        r"impossible to reach",
    ],
    "callback": [
        r"never (?:called|got|rang) (?:me )?back",
        r"(?:didn'?t|did not|won'?t|will not|wouldn'?t|would not) (?:call|get) (?:me )?back",
        r"no (?:call|callback|return call)",
        r"never returned (?:my )?call",
        r"still waiting (?:for|on) a call",
    ],
    "slow_response": [
        r"slow to respond",
        r"(?:very |so )?unresponsive",
        r"non[- ]?responsive",
        r"hard to (?:reach|get hold|get a hold)",
        r"took (?:days|forever|ages|weeks)",
        r"days to (?:respond|reply|call)",
    ],
    "after_hours": [
        r"after hours? (?:no|nobody|no one|can'?t)",
        r"(?:weekend|evening|night).{0,20}(?:no answer|couldn'?t reach|closed)",
    ],
}

_COMPILED: dict[str, list[re.Pattern]] = {
    cat: [re.compile(p, re.IGNORECASE) for p in pats]
    for cat, pats in _REVIEW_PATTERNS.items()
}

# Words signalling the business claims urgent / round-the-clock availability.
_EMERGENCY_CLAIM = re.compile(
    r"24[/ ]?7|24 ?hour|around the clock|emergency|same[- ]day|anytime|always (?:available|open)",
    re.IGNORECASE,
)


def _categorise_review(text: str) -> list[str]:
    """Return the responsiveness-complaint categories a review text matches."""
    if not text:
        return []
    hits = []
    for cat, patterns in _COMPILED.items():
        if any(p.search(text) for p in patterns):
            hits.append(cat)
    return hits


def _short_quote(text: str, max_len: int = 140) -> str:
    quote = re.sub(r"\s+", " ", text).strip()
    if len(quote) > max_len:
        quote = quote[: max_len - 1].rstrip() + "…"
    return quote


def _has_after_hours_gap(intel: dict[str, Any], opening_hours: Any) -> bool:
    """True if the business signals urgency but has limited published hours.

    A contractor that advertises emergency / 24-7 service but lists ordinary
    9-5 weekday hours (or no weekend hours) almost certainly drops after-hours
    calls — a textbook Owlbell fit.
    """
    claims_urgency = bool(intel.get("has_emergency_service"))
    weekday_text: list[str] = []
    if isinstance(opening_hours, dict):
        weekday_text = opening_hours.get("weekday_text") or []
    elif isinstance(opening_hours, list):
        weekday_text = opening_hours

    if not claims_urgency or not weekday_text:
        return False

    joined = " ".join(weekday_text).lower()
    advertises_24_7 = "open 24 hours" in joined
    # Closed at least one weekend day, or not open 24h → gap exists.
    mentions_weekend_closed = "closed" in joined
    return claims_urgency and not advertises_24_7 and (mentions_weekend_closed or "open 24 hours" not in joined)


class SignalAgent:
    """Detects fresh, observable buying triggers for a lead."""

    def detect(self, lead: dict[str, Any]) -> dict[str, Any]:
        intel = lead.get("_intelligence", {}) or {}
        reviews = lead.get("reviews") or []
        opening_hours = lead.get("opening_hours")
        rating = lead.get("rating")
        review_count = lead.get("review_count") or 0

        # ── Mine review text ──────────────────────────────────────
        matched: list[dict[str, str]] = []
        category_counts: dict[str, int] = {}
        for r in reviews:
            text = r.get("text", "") if isinstance(r, dict) else str(r)
            cats = _categorise_review(text)
            if not cats:
                continue
            for c in cats:
                category_counts[c] = category_counts.get(c, 0) + 1
            matched.append(
                {
                    "quote": _short_quote(text),
                    "categories": ",".join(cats),
                    "rating": str(r.get("rating", "")) if isinstance(r, dict) else "",
                }
            )

        reviews_analyzed = len(reviews)
        complaints = len(matched)

        # ── Other observable signals ──────────────────────────────
        after_hours_gap = _has_after_hours_gap(intel, opening_hours)
        no_online_booking = intel.get("has_online_booking") is False
        phone_dependent = intel.get("phone_prominence") in (
            "header",
            "click_to_call",
            "sticky",
        ) or bool(intel.get("calls_matter"))

        # ── Scores ────────────────────────────────────────────────
        # Missed-call risk: dominated by review evidence, nudged by low rating.
        if reviews_analyzed:
            risk = min(1.0, complaints / reviews_analyzed + (0.15 if complaints else 0.0))
        else:
            risk = 0.0
        if rating is not None and rating < 4.0 and complaints:
            risk = min(1.0, risk + 0.1)

        # ── Human-readable triggers (truthful, evidence-backed) ───
        triggers: list[str] = []
        if complaints:
            label = _category_phrase(category_counts)
            triggers.append(
                f"{complaints} of {reviews_analyzed} recent Google reviews mention {label}"
            )
        if after_hours_gap:
            triggers.append(
                "Advertises emergency/urgent service but published hours leave after-hours calls uncovered"
            )
        if no_online_booking and phone_dependent:
            triggers.append(
                "Phone is the primary way to reach them, with no online booking fallback"
            )

        # Overall signal strength: is there a *fresh reason* to reach out?
        signal_score = max(
            risk,
            0.6 if after_hours_gap else 0.0,
            0.4 if (no_online_booking and phone_dependent) else 0.0,
        )

        return {
            "missed_call_risk": round(risk, 3),
            "signal_score": round(signal_score, 3),
            "review_signals": {
                "reviews_analyzed": reviews_analyzed,
                "responsiveness_complaints": complaints,
                "category_counts": category_counts,
                "matched_reviews": matched[:5],
            },
            "after_hours_gap": after_hours_gap,
            "no_online_booking": bool(no_online_booking),
            "phone_dependent": bool(phone_dependent),
            "triggers": triggers,
            "has_fresh_trigger": bool(triggers),
            "_detected_at": datetime.now(timezone.utc).isoformat(),
        }

    def detect_and_enrich(self, lead: dict[str, Any]) -> dict[str, Any]:
        """Attach `_signals` and fold triggers into intelligence observations."""
        signals = self.detect(lead)
        enriched = {
            **lead,
            "_signals": signals,
            "_missed_call_risk": signals["missed_call_risk"],
            "_signal_score": signals["signal_score"],
        }

        # Make triggers visible to the existing agents that read observations.
        if signals["triggers"]:
            intel = dict(enriched.get("_intelligence") or {})
            existing = intel.get("observations") or ""
            trigger_text = " SIGNALS: " + "; ".join(signals["triggers"])
            intel["observations"] = (existing + trigger_text).strip()
            enriched["_intelligence"] = intel

        return enriched

    def detect_many(self, leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for lead in leads:
            enriched = self.detect_and_enrich(lead)
            results.append(enriched)
            logger.info(
                "signals.detected",
                name=lead.get("name"),
                risk=enriched["_missed_call_risk"],
                triggers=len(enriched["_signals"]["triggers"]),
            )
        return results


def _category_phrase(counts: dict[str, int]) -> str:
    """Turn category counts into a readable phrase for a trigger string."""
    labels = {
        "voicemail": "calls going to voicemail",
        "no_answer": "no one answering the phone",
        "callback": "not getting a call back",
        "slow_response": "slow or hard-to-reach responsiveness",
        "after_hours": "no after-hours availability",
    }
    if not counts:
        return "responsiveness problems"
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return labels.get(top[0][0], "responsiveness problems")
