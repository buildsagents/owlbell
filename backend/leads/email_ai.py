"""AI-powered email personalization and reply handling using Groq (free, fast inference API)."""

from __future__ import annotations

from typing import Any, Optional

import structlog
from openai import AsyncOpenAI

from backend.config import get_settings

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are Owlbell's AI sales rep. Your job is to help contractors
(HVAC, plumbing, roofing, electrical, etc.) understand they're losing jobs to missed calls.

TONE RULES:
- Professional but conversational. Like a contractor talking to another contractor.
- NEVER hype, NEVER pushy. State facts plainly.
- Use short sentences. No fluff.
- Reference their specific business, location, and trade.
- The goal is to get them to visit owlbell.xyz/pricing

WHEN SOMEONE REPLIES:
- If they say "not interested" → politely bow out, leave the door open
- If they ask "how much" → say $297/mo, 30-day guarantee, mention one job pays for the year
- If they ask "how it works" → explain: forward your number, we answer 24/7 in your name, you get text/email of every call
- If they raise an objection → address it directly, don't dodge
- If they seem interested → invite them to owlbell.xyz/pricing
"""

GENERATE_PROMPT = """Write a short cold email (max 150 words) for {business_name}, a {trade} contractor in {city}, {state}.

Business context: {business_context}

The email should:
- Reference their business by name
- Mention you noticed they're busy (not that they missed calls — that sounds accusatory)
- Talk about how hard it is to answer phones while on the job
- Mention Owlbell solves this
- End with owlbell.xyz/pricing?ref=lead

Sign as one of: Mike, Dave, Chris, Pat, Steve, Tony, Jesse, Ryan (pick randomly).

NO greetings like "I hope this email finds you well". Just get to the point."""

REPLY_CLASSIFY_PROMPT = """Classify this email reply from a contractor we cold-emailed about our call-answering service (Owlbell).

Reply: {reply}

Choose ONE label:
- interested: They want to learn more, ask about pricing, ask how it works
- not_interested: Polite or direct "no", "not interested", "stop emailing me"
- objection: They raise a concern (too expensive, already have someone, don't need it)
- question: They ask a specific question about features, pricing, setup
- unsubscribe: They explicitly ask to be removed
- neutral: Can't tell / unrelated

Respond with JUST the label, no explanation."""

RESPONSE_PROMPT = """Write a reply to this contractor's email about our call-answering service Owlbell.

Their business: {business_name} ({trade} in {city}, {state})
Their original reply: {reply}
Classification: {classification}

Guidelines:
- Keep it short (3-4 sentences max)
- Address their specific point directly
- If interested → explain next step: owlbell.xyz/pricing
- If objection → address it honestly, don't dodge
- If not interested → one sentence respecting their decision, leave door open
- Sound like a real person, not a sales bot
- Sign with a random name from: Mike, Dave, Chris, Pat, Steve, Tony, Jesse, Ryan"""

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


def is_configured() -> bool:
    return bool(get_settings().integrations.groq_api_key)


async def _chat(messages: list[dict], temperature: float = 0.7, max_tokens: int = 500) -> Optional[str]:
    client = _get_client()
    if not client:
        return None
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("ai.chat_error", error=str(exc))
        return None


async def generate_email(
    business_name: str,
    trade: str,
    city: str,
    state: str,
    website: Optional[str] = None,
) -> Optional[str]:
    business_context = f"{trade} contractor in {city}, {state}"
    if website:
        business_context += f". Website: {website}"

    prompt = GENERATE_PROMPT.format(
        business_name=business_name,
        trade=trade,
        city=city,
        state=state,
        business_context=business_context,
    )

    return await _chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        max_tokens=500,
    )


async def classify_reply(reply_text: str) -> str:
    prompt = REPLY_CLASSIFY_PROMPT.format(reply=reply_text)
    result = await _chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=20,
    )
    return result.lower() if result else "neutral"


async def generate_reply(
    business_name: str,
    trade: str,
    city: str,
    state: str,
    reply_text: str,
    classification: str,
) -> Optional[str]:
    prompt = RESPONSE_PROMPT.format(
        business_name=business_name,
        trade=trade,
        city=city,
        state=state,
        reply=reply_text,
        classification=classification,
    )

    return await _chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=500,
    )


async def personalize_lead(lead: dict[str, Any]) -> dict[str, Any]:
    """Add AI-generated email body to a lead."""
    if not is_configured():
        return lead

    body = await generate_email(
        business_name=lead.get("name", "your business"),
        trade=lead.get("trade", "contractor"),
        city=lead.get("city", "your area"),
        state=lead.get("state", ""),
        website=lead.get("website"),
    )
    if body:
        lead["_ai_body"] = body
    return lead
