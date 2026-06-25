from __future__ import annotations

import asyncio
from typing import Any, Optional

import structlog

from backend.leads.email_sender import send_email, is_configured as smtp_configured
from backend.leads import lead_store

logger = structlog.get_logger(__name__)

DAILY_CAP = 80

SUBJECT_LINES = [
    "{business} — missed calls are costing you jobs",
    "{business}, quick question about your phone",
    "Your phone at {business}",
    "Busy contractors lose leads",
    "You're leaving money on the table, {first_name}",
    "{business} deserves more calls",
]

TRADE_SPECIFIC = {
    "hvac": {
        "suffix": "HVAC",
        "pain": "When you're on a roof swapping a condenser and your office phone rings, that's a booked job going to voicemail.",
        "outcome": "Every call gets answered, emergency dispatches get triaged, and you stay on the tools.",
    },
    "plumbing": {
        "suffix": "Plumbing",
        "pain": "When you're elbow-deep in a drain line and the phone rings, that's an emergency repair walking out the door.",
        "outcome": "Every call gets answered — leak, clog, or consult — and you stay on the wrench.",
    },
    "roofing": {
        "suffix": "Roofing",
        "pain": "When you're on a roof and the phone rings, you can't answer. That hail-damage inspection just called your competitor.",
        "outcome": "Every call gets answered, estimates get booked, and you stay on the ridge.",
    },
    "electrical": {
        "suffix": "Electrical",
        "pain": "When you're up in a ceiling pulling wire and the phone rings, that panel upgrade just called someone else.",
        "outcome": "Every call gets answered, service calls get scheduled, and you stay on the job.",
    },
    "general": {
        "suffix": "Contractor",
        "pain": "When you're on-site with a crew and the phone rings, that new bid just went to voicemail.",
        "outcome": "Every call gets answered, bids get booked, and you stay on site.",
    },
    "landscaping": {
        "suffix": "Landscaping",
        "pain": "When you're behind a mower and the phone rings, that design consult just called your competitor.",
        "outcome": "Every call gets answered, estimates get scheduled, and you stay on the crew.",
    },
    "painting": {
        "suffix": "Painting",
        "pain": "When you're on a ladder with a roller and the phone rings, that interior job just went to voicemail.",
        "outcome": "Every call gets answered, walkthroughs get booked, and you stay painting.",
    },
    "pest_control": {
        "suffix": "Pest Control",
        "pain": "When you're in a crawlspace and the phone rings, that termite inspection just called your competitor.",
        "outcome": "Every call gets answered, treatments get scheduled, and you stay in the field.",
    },
    "flooring": {
        "suffix": "Flooring",
        "pain": "When you're knee-deep in a tile layout and the phone rings, that hardwood install just went to voicemail.",
        "outcome": "Every call gets answered, estimates get booked, and you stay on the install.",
    },
    "gutters": {
        "suffix": "Gutters",
        "pain": "When you're on a ladder running gutter and the phone rings, that leaf-guard job just called someone else.",
        "outcome": "Every call gets answered, estimates get scheduled, and you stay on the ladder.",
    },
}

INITIAL_TEMPLATES = [
    """Hi {first_name},

We checked on {business} and noticed your phone line isn't being answered right now — which makes sense, you're busy on the job.

But here's the problem: every call you miss goes straight to voicemail, and 8 out of 10 voicemails never get a callback. That's jobs walking out the door without you even knowing they called.

{trade_pain}

Owlbell answers every call 24/7 in your business name. Books appointments. Texts you the details. All automated. From $297/month — one job pays for it for the entire year.

You don't install anything. You don't learn anything. You forward one number and go back to work. 30-day money-back guarantee.

See how it works: https://owlbell.xyz/pricing?ref=lead&src=email&trade={trade_key}

— Mike""",

    """Hi {first_name},

I was looking at {business} today and noticed something — your phone rings but nobody picks up. You're probably out on a job working. That's the right move. But your customers don't care you're busy. They just call the next guy.

{trade_pain}

You need someone to answer for you. That's what Owlbell does. We answer every call in your business name, 24/7. We book appointments to your calendar. We text you what happened. You just work.

{dollars_lost_per_year} a year is what missed calls cost a business like yours. Owlbell is $297/month. Do the math.

No meetings. No setup calls. No training.

https://owlbell.xyz/pricing?ref=lead&src=email&trade={trade_key}

— Dave""",

    """Subject: {business}, we tried calling

Hi {first_name},

Called {business} today — nobody picked up. I get it, you're working. But every voicemail is a lead you're handing to a competitor.

{trade_pain}

I built Owlbell because I watched too many good contractors lose jobs they never even knew existed. The phone rings while you're working, goes to voicemail, and that job calls the next guy.

Owlbell fixes it. Answers every call in your name. Books jobs. Texts you. From $297/month.

30-day guarantee. If you don't get more calls booked, you don't pay.

https://owlbell.xyz/pricing?ref=lead&src=email&trade={trade_key}

— Chris""",
]

FOLLOWUP_1_TEMPLATES = [
    """Hi {first_name},

I reached out a few days ago about {business} missing calls. You're busy — I get it. That's actually the whole point.

What if every call you missed this week had been answered? Booked to your calendar. Ready for you when you got back to the truck.

That's what Owlbell does. And while you're reading this, contractors in {city} are already using it to catch jobs they'd otherwise lose.

{competitor_pitch}

One job pays for a whole year. 30-day money-back guarantee. You've got nothing to lose but missed calls.

https://owlbell.xyz/pricing?ref=lead&src=email&trade={trade_key}&f=1

— Pat""",

    """Hi {first_name},

Quick follow-up about {business}.

You're probably thinking "I don't have time for another app or service." Fair. But Owlbell isn't that.

You forward one number. That's it. No dashboard to check. No software to learn. Calls get answered, jobs get booked, and you get a text with the details.

{business} in {city} deserves every call that comes in. Don't let them go to voicemail.

https://owlbell.xyz/pricing?ref=lead&src=email&trade={trade_key}&f=1

— Steve""",

    """Hi {first_name},

One more thought about {business}.

You're the best {trade_label} in {city}. Your work is solid. But if people can't reach you, they don't know that. They call the next guy who answers.

Owlbell makes sure you never miss a call again. 24/7. In your business name. Books appointments. Costs $297/month — less than you'd make on half a service call.

Contractors using Owlbell aren't telling their competitors. You found us first.

https://owlbell.xyz/pricing?ref=lead&src=email&trade={trade_key}&f=1

— Tony""",
]

FOLLOWUP_2_TEMPLATES = [
    """Hi {first_name},

Last time I'll reach out about {business}.

Here's the truth: you're losing jobs every single day to missed calls. I know it, you know it. The question is whether you want to fix it.

Owlbell answers every call 24/7. {trade_outcome}

One job covers the cost for a year. If you don't book more jobs in 30 days, you don't pay a cent.

The offer stands. The phone's still ringing. The calls are still going to voicemail.

https://owlbell.xyz/pricing?ref=lead&src=email&trade={trade_key}&f=2

— Jesse""",

    """Hi {first_name},

This is my last email about {business}.

I'm not going to keep bothering you — you've got work to do. But I want you to remember one thing:

Every call you miss is a job your competitor books. That's not a sales pitch, that's just how contracting works.

Owlbell answers for you. $297/month. 30-day guarantee. You forward your number and go back to work.

If you ever want to stop losing calls to voicemail, you know where to find us.

https://owlbell.xyz/pricing?ref=lead&src=email&trade={trade_key}&f=2

— Ryan""",
]

SENDER_NAMES = ["Mike", "Dave", "Chris", "Pat", "Steve", "Tony", "Jesse", "Ryan"]


def _trade_key(trade: Optional[str]) -> str:
    t = (trade or "").lower().strip()
    return t if t in TRADE_SPECIFIC else "general"


async def send_initial(lead: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    first_name = (lead.get("name") or "there").split()[0]
    business = lead.get("name") or "your business"
    city = lead.get("city") or "your area"
    trade = lead.get("trade") or ""
    trade_key = _trade_key(trade)
    trade_info = TRADE_SPECIFIC[trade_key]
    trade_label = trade_info["suffix"]
    trade_pain = trade_info["pain"]
    trade_outcome = trade_info["outcome"]

    competition = f"The contractor down the street from you in {city} already answers 24/7. Are you going to let them take your calls?"

    idx = lead.get("_seen_count", 0) % len(INITIAL_TEMPLATES)
    subject = SUBJECT_LINES[idx % len(SUBJECT_LINES)].format(business=business)
    body = INITIAL_TEMPLATES[idx].format(
        first_name=first_name,
        business=business,
        city=city,
        trade_key=trade_key,
        trade_label=trade_label,
        trade_pain=trade_pain,
        trade_outcome=trade_outcome,
        competitor_pitch=competition,
        dollars_lost_per_year="$52,000",
    )

    if dry_run:
        logger.info("outreach.dry_run", to=lead.get("email"), business=business, subject=subject)
        return {"success": True, "dry_run": True, "subject": subject, "body_preview": body[:100]}

    result = await send_email(
        to_email=lead["email"],
        to_name=first_name,
        subject=subject,
        body_text=body,
    )
    return result


async def send_followup(lead: dict[str, Any], stage: int, dry_run: bool = False) -> dict[str, Any]:
    templates = FOLLOWUP_1_TEMPLATES if stage == 1 else FOLLOWUP_2_TEMPLATES
    first_name = (lead.get("name") or "there").split()[0]
    business = lead.get("name") or "your business"
    city = lead.get("city") or "your area"
    trade = lead.get("trade") or ""
    trade_key = _trade_key(trade)
    trade_info = TRADE_SPECIFIC[trade_key]
    trade_label = trade_info["suffix"]
    trade_outcome = trade_info["outcome"]

    competition = f"While you're deciding, contractors all over {city} are already using Owlbell. They're not telling their competitors."

    idx = (stage + lead.get("_seen_count", 0)) % len(templates)
    subject = SUBJECT_LINES[(idx + len(SUBJECT_LINES) // 2) % len(SUBJECT_LINES)].format(business=business)
    body = templates[idx].format(
        first_name=first_name,
        business=business,
        city=city,
        trade_key=trade_key,
        trade_label=trade_label,
        trade_pain=trade_info["pain"],
        trade_outcome=trade_outcome,
        competitor_pitch=competition,
        dollars_lost_per_year="$52,000",
    )

    if dry_run:
        logger.info("outreach.dry_run_followup", to=lead.get("email"), business=business, stage=stage)
        return {"success": True, "dry_run": True}

    result = await send_email(
        to_email=lead["email"],
        to_name=first_name,
        subject=subject,
        body_text=body,
    )
    return result


async def send_initial_outreach(
    leads: list[dict[str, Any]],
    max_per_day: int = DAILY_CAP,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    sent_count = 0
    results = []

    for lead in leads:
        email = lead.get("email")
        if not email:
            lead["outreach_status"] = "skipped_no_email"
            results.append(lead)
            continue

        if lead_store.get_lead(email) and lead_store.get_lead(email).get("status") not in ("new",):
            lead["outreach_status"] = "skipped_already_contacted"
            results.append(lead)
            continue

        if sent_count >= max_per_day:
            lead["outreach_status"] = "skipped_daily_cap"
            results.append(lead)
            continue

        lead_store.add_lead(lead)

        result = await send_initial(lead, dry_run=dry_run)

        if result.get("success") and not dry_run:
            lead_store.mark_sent(email)
            sent_count += 1
            lead["outreach_status"] = "sent"
        elif dry_run:
            lead["outreach_status"] = "dry_run"
            sent_count += 1
        else:
            lead["outreach_status"] = f"failed: {result.get('error', 'unknown')}"

        results.append(lead)
        await asyncio.sleep(1)

    logger.info("outreach.initial_complete", sent=sent_count, total=len(leads), dry_run=dry_run)
    return results


async def send_followups(
    max_per_day: int = DAILY_CAP,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    pending = lead_store.get_pending_follow_ups()
    if not pending:
        logger.info("outreach.no_followups_pending")
        return []

    sent_count = 0
    results = []

    for lead in pending:
        if sent_count >= max_per_day:
            break

        stage = lead.get("follow_up_stage", 0) + 1
        result = await send_followup(lead, stage, dry_run=dry_run)

        if result.get("success") and not dry_run:
            lead_store.mark_follow_up_sent(lead["email"])
            sent_count += 1
            lead["outreach_status"] = f"followup_{stage}"
        elif dry_run:
            lead["outreach_status"] = "dry_run_followup"
            sent_count += 1
        else:
            lead["outreach_status"] = f"failed: {result.get('error', 'unknown')}"

        results.append(lead)
        await asyncio.sleep(1)

    logger.info("outreach.followup_complete", sent=sent_count, total=len(pending), dry_run=dry_run)
    return results


def get_stats() -> dict[str, Any]:
    return lead_store.stats()
