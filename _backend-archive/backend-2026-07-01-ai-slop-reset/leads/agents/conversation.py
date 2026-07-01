from __future__ import annotations

import json
import re
from typing import Any, Optional

import structlog
from openai import AsyncOpenAI

from backend.config import get_settings

logger = structlog.get_logger(__name__)

CLASSIFY_PROMPT = """Classify this reply from a plumbing company we emailed about Owlbell (AI phone receptionist for plumbers).

BUSINESS: {business_name}
REPLY: {reply}

Choose ONE:
- interested: Want to learn more, ask pricing, ask how it works
- not_interested: Polite or direct no
- objection: Raise a specific concern
- question: Ask a specific question
- unsubscribe: Want to be removed
- meeting_request: Want to hop on a call
- neutral: Can't tell / unrelated

Respond with JSON:
{{
  "classification": "...",
  "brief_reason": "One sentence explaining why",
  "urgency": "low | medium | high"
}}

Return ONLY valid JSON."""

RESPOND_PROMPT = """Write a reply to this plumbing company's email about Owlbell (AI phone receptionist for plumbers).

BUSINESS: {business_name}
INDUSTRY: {industry}
INTELLIGENCE: Services: {services}, Has emergency service: {has_emergency}, Phone prominent: {phone_prominence}
THEIR REPLY: {reply}
CLASSIFICATION: {classification}

GUIDELINES:
- 3-4 sentences max
- Address their specific point
- If interested → explain next step: owlbell.xyz/pricing
- If objection → address honestly, reference their business if relevant
- If meeting_request → suggest a quick call
- If not interested → one sentence, leave door open
- Sound like a real person, not a bot
- Sign with a first name only

Return JSON:
{{
  "reply_body": "Your reply text here",
  "action": "send | flag_for_human | escalate",
  "action_reason": "Why this action was chosen",
  "suggest_meeting": true|false
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


class ConversationAgent:
    def __init__(self):
        self._client = _get_client()

    async def classify(self, lead: dict[str, Any], reply_text: str) -> dict[str, Any]:
        prompt = CLASSIFY_PROMPT.format(
            business_name=lead.get("name", "Unknown"),
            reply=reply_text,
        )

        if not self._client:
            return self._classify_heuristic(reply_text)

        try:
            response = await self._client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=150,
            )
            text = response.choices[0].message.content.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            return json.loads(text)
        except Exception as exc:
            logger.error("conversation.classify_error", error=str(exc))
            return self._classify_heuristic(reply_text)

    def _classify_heuristic(self, reply_text: str) -> dict[str, Any]:
        lower = reply_text.lower()
        if any(w in lower for w in ["unsubscribe", "stop", "remove", "don't email"]):
            return {"classification": "unsubscribe", "brief_reason": "Explicit unsubscribe request", "urgency": "low"}
        if any(w in lower for w in ["not interested", "no thanks", "stop emailing", "leave me alone"]):
            return {"classification": "not_interested", "brief_reason": "Declined", "urgency": "low"}
        if any(w in lower for w in ["how much", "pricing", "cost", "price", "monthly"]):
            return {"classification": "question", "brief_reason": "Asking about pricing", "urgency": "medium"}
        if any(w in lower for w in ["tell me more", "how it works", "interested", "yes", "sign me up"]):
            return {"classification": "interested", "brief_reason": "Positive signal", "urgency": "high"}
        if any(w in lower for w in ["call", "meeting", "demo", "talk", "chat", "hop on"]):
            return {"classification": "meeting_request", "brief_reason": "Requesting a conversation", "urgency": "high"}
        if any(w in lower for w in ["too expensive", "already have", "tried before", "don't need"]):
            return {"classification": "objection", "brief_reason": "Raised a concern", "urgency": "medium"}
        return {"classification": "neutral", "brief_reason": "Could not determine intent", "urgency": "low"}

    async def respond(
        self,
        lead: dict[str, Any],
        reply_text: str,
        classification: str,
    ) -> dict[str, Any]:
        intel = lead.get("_intelligence", {}) or {}

        prompt = RESPOND_PROMPT.format(
            business_name=lead.get("name", "Unknown"),
            industry="plumbing",
            services=json.dumps(intel.get("services", [])[:3]),
            has_emergency=intel.get("has_emergency_service", False),
            phone_prominence=intel.get("phone_prominence", "unknown"),
            reply=reply_text,
            classification=classification,
        )

        if not self._client:
            return self._respond_heuristic(lead, reply_text, classification)

        try:
            response = await self._client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=500,
            )
            text = response.choices[0].message.content.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            return json.loads(text)
        except Exception as exc:
            logger.error("conversation.respond_error", error=str(exc))
            return self._respond_heuristic(lead, reply_text, classification)

    def _respond_heuristic(
        self,
        lead: dict[str, Any],
        reply_text: str,
        classification: str,
    ) -> dict[str, Any]:
        name = lead.get("name", "your business")

        if classification == "interested":
            return {
                "reply_body": f"Thanks for the interest! Here's the quick version: you forward your number to us, we answer every call in your business's name 24/7, book appointments on your calendar, and text you the details. $297/month, 30-day guarantee. Check it out: owlbell.xyz/pricing — Mike",
                "action": "send",
                "action_reason": "Interested lead — send info",
                "suggest_meeting": False,
            }
        elif classification == "question":
            return {
                "reply_body": f"Great question. Owlbell answers every call in your name — not a generic service. It knows your hours, services, service areas, and can book appointments on your actual calendar. $297/mo for Basic (500 calls), $797/mo for Pro (2,000 calls + booking + calendar sync). 30-day guarantee. owlbell.xyz/pricing — Dave",
                "action": "send",
                "action_reason": "Answered their question",
                "suggest_meeting": False,
            }
        elif classification == "meeting_request":
            return {
                "reply_body": f"Happy to chat! You can pick a time that works here: https://cal.com/answerflow/demo — or I can answer quick questions over email. Either works. — Chris",
                "action": "send",
                "action_reason": "Suggesting meeting link",
                "suggest_meeting": True,
            }
        elif classification == "objection":
            return {
                "reply_body": f"Fair concern. The way I'd look at it: one extra job per year covers the cost. And with the 30-day guarantee, there's zero risk. If it doesn't bring in more calls, you don't pay. Happy to jump on a quick call if that helps. owlbell.xyz/pricing — Pat",
                "action": "send",
                "action_reason": "Addressed objection",
                "suggest_meeting": False,
            }
        elif classification == "not_interested":
            return {
                "reply_body": f"No worries, {name}. If things change down the road, feel free to reach out. owlbell.xyz — Mike",
                "action": "send",
                "action_reason": "Respecting their decision",
                "suggest_meeting": False,
            }
        elif classification == "unsubscribe":
            return {
                "reply_body": f"You've been unsubscribed. Sorry for the bother. — Owlbell",
                "action": "send",
                "action_reason": "Unsubscribe request honored",
                "suggest_meeting": False,
            }
        return {
            "reply_body": f"Thanks for the reply! If you're curious about Owlbell, you can see all the details at owlbell.xyz/pricing. Happy to answer any questions. — Mike",
            "action": "send",
            "action_reason": "Default response for neutral reply",
            "suggest_meeting": False,
        }

    async def handle_reply(
        self,
        lead: dict[str, Any],
        reply_text: str,
    ) -> dict[str, Any]:
        classification_result = await self.classify(lead, reply_text)
        cls = classification_result.get("classification", "neutral")

        if cls == "unsubscribe":
            return {
                "classification": classification_result,
                "response": {
                    "reply_body": "You've been unsubscribed. Sorry for the bother. — Owlbell",
                    "action": "unsubscribe",
                    "action_reason": "Honoring unsubscribe request",
                    "suggest_meeting": False,
                },
            }

        response_result = await self.respond(lead, reply_text, cls)
        trigger_onboarding = cls == "interested" and response_result.get("suggest_meeting") is False

        return {
            "classification": classification_result,
            "response": response_result,
            "trigger_onboarding": trigger_onboarding,
        }
