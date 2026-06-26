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

SCORE_PROMPT = """You are a lead scoring AI for a cold email outreach platform. Score this contractor lead from 1 (worst) to 10 (best) based on how likely they are to convert.

Lead data:
- Name: {name}
- Trade: {trade}
- City: {city}, {state}
- Website: {website}
- Phone: {phone}
- Rating: {rating}/5
- Reviews: {review_count}
- Business status: {business_status}

Scoring rules:
- +2 if they have a professional website (not just Facebook/Yelp)
- +1 if they have a phone number
- +1 if rating >= 4.0
- +1 if review_count >= 20
- +1 if business_status is OPERATIONAL
- +2 if they invest in their online presence (website has blog, pricing, or service pages)
- -1 if no website found
- -2 if business_status is CLOSED_TEMPORARILY or CLOSED_PERMANENTLY

Respond with JUST a number 1-10. No explanation."""

SCORE_WITH_WEBSITE_PROMPT = """Analyze this contractor's website and update their lead score.

Business: {name} ({trade}, {city}, {state})
Website: {website}

Check:
- Does the site look professional?
- Does it have a blog or service pages?
- Does it have pricing info?
- Is the site modern or outdated?
- Does it have a contact form or online booking?

Brief analysis (1 sentence), then score 1-10 on a new line."""

FOLLOWUP_1_PROMPT = """Write a follow-up email (max 120 words) for {business_name}, a {trade} contractor in {city}, {state}.

Context: We sent them a cold email {days_since} days ago about Owlbell (24/7 call answering for contractors). They didn't reply.

The email should:
- Reference the previous email naturally (not "did you get my email")
- Use a different angle than "you're missing calls"
- Mention that other {trade} contractors in {city} are already using it
- Keep it short and respectful
- End with owlbell.xyz/pricing?ref=lead&f=1

Sign as: Mike, Dave, Chris, Pat, Steve, Tony, Jesse, or Ryan (pick different from previous).
NO greetings. Direct and conversational."""

FOLLOWUP_2_PROMPT = """Write a second follow-up email (max 100 words) for {business_name}, a {trade} contractor in {city}, {state}.

Context: They haven't replied to two previous emails about Owlbell (24/7 call answering for contractors).

The email should:
- Be short and direct
- Lead with social proof ("Contractors in {city} are adding $Xk/month with Owlbell")
- Include urgency ("prices increase next month")
- End with owlbell.xyz/pricing?ref=lead&f=2

Sign as someone different from the previous two emails.
NO greetings. Punchy and memorable."""

FOLLOWUP_3_PROMPT = """Write a final follow-up email (max 80 words) for {business_name}, a {trade} contractor in {city}, {state}.

This is the LAST email they'll get from us about Owlbell.

The email should:
- Be respectful and not pushy
- Leave the door open
- One last clear value proposition
- End with owlbell.xyz/pricing?ref=lead&f=3

Sign off. Make it clear this is the last time they'll hear from us.

NO greetings. Brief and classy."""

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


async def score_lead(lead: dict[str, Any]) -> int:
    """AI-powered lead scoring 1-10."""
    prompt = SCORE_PROMPT.format(
        name=lead.get("name", "Unknown"),
        trade=lead.get("trade", "contractor"),
        city=lead.get("city", "Unknown"),
        state=lead.get("state", ""),
        website=lead.get("website", "none"),
        phone=lead.get("phone", "none"),
        rating=lead.get("rating", 0),
        review_count=lead.get("review_count", 0),
        business_status=lead.get("business_status", "UNKNOWN"),
    )
    result = await _chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=10,
    )
    if result:
        try:
            return max(1, min(10, int(result.strip())))
        except ValueError:
            pass
    return 5


async def generate_followup(lead: dict[str, Any], stage: int, days_since: int) -> Optional[str]:
    """Generate an AI follow-up email for a lead at a given stage."""
    prompts = {1: FOLLOWUP_1_PROMPT, 2: FOLLOWUP_2_PROMPT, 3: FOLLOWUP_3_PROMPT}
    prompt_template = prompts.get(stage)
    if not prompt_template:
        return None

    prompt = prompt_template.format(
        business_name=lead.get("name", "your business"),
        trade=lead.get("trade", "contractor"),
        city=lead.get("city", "your area"),
        state=lead.get("state", ""),
        days_since=days_since,
    )

    return await _chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.8,
        max_tokens=400,
    )


async def generate_subject(
    business_name: str,
    trade: str,
    city: str,
    stage: int = 0,
) -> Optional[str]:
    """Generate a unique subject line for a lead."""
    stage_label = ["initial", "followup_1", "followup_2", "final"][min(stage, 3)]
    prompt = f"""Write one short email subject line (max 8 words) for a cold email to {business_name}, a {trade} contractor in {city}.

Stage: {stage_label}
If initial: reference their business, NOT "missed calls"
If follow-up: reference previous contact naturally

No clickbait. No ALL CAPS. Sound like a person. One line only."""
    return await _chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=30,
    )
