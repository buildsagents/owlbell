"""Check for replies to our sent emails and handle them with AI."""

from __future__ import annotations

import base64
from typing import Any, Optional

import httpx
import structlog

from backend.config import get_settings
from backend.integrations.gmail.service import is_configured as gmail_configured
from backend.integrations.gmail.service import _get_access_token
from backend.leads import lead_store
from backend.leads.email_ai import classify_reply, generate_reply, is_configured as ai_configured
from backend.leads.email_sender import send_email

logger = structlog.get_logger(__name__)

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"


async def _gmail_request(method: str, path: str, **kwargs) -> Optional[dict]:
    token = await _get_access_token()
    if not token:
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.request(
            method,
            f"{GMAIL_API_BASE}/{path}",
            headers={"Authorization": f"Bearer {token}"},
            **kwargs,
        )
    if resp.status_code >= 400:
        logger.warning("gmail.request_error", path=path, status=resp.status_code)
        return None
    return resp.json()


async def check_for_replies() -> list[dict[str, Any]]:
    """Scan Gmail inbox for replies to our sent emails."""
    if not gmail_configured():
        logger.warning("reply.gmail_not_configured")
        return []

    # Get all leads we've emailed
    sent_leads = lead_store.get_all_sent()
    if not sent_leads:
        return []

    # Search for recent replies (last 24h)
    results = await _gmail_request("GET", "users/me/messages?q=in:inbox after:1d")
    if not results or "messages" not in results:
        return []

    replies = []
    for msg_info in results["messages"][:20]:
        msg = await _gmail_request("GET", f"users/me/messages/{msg_info['id']}")
        if not msg:
            continue

        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("subject", "")
        sender = headers.get("from", "")
        reply_to = headers.get("in-reply-to", "")

        # Check if this is a reply to one of our emails
        matched_lead = None
        for lead in sent_leads:
            if lead.get("email") and lead["email"] in sender.lower():
                matched_lead = lead
                break

        if not matched_lead:
            continue

        # Decode body
        body = _extract_body(msg)
        if not body:
            continue

        replies.append({
            "message_id": msg_info["id"],
            "thread_id": msg.get("threadId"),
            "from": sender,
            "subject": subject,
            "body": body,
            "lead": matched_lead,
        })

    return replies


def _extract_body(msg: dict) -> Optional[str]:
    """Extract plain text from a Gmail API message."""
    try:
        parts = msg.get("payload", {}).get("parts", [])
        if not parts:
            data = msg.get("payload", {}).get("body", {}).get("data", "")
        else:
            data = ""
            for p in parts:
                if p.get("mimeType") == "text/plain":
                    data = p.get("body", {}).get("data", "")
                    break
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    except Exception:
        pass
    return None


async def handle_replies() -> dict[str, Any]:
    """Check for replies and respond with AI."""
    replies = await check_for_replies()
    if not replies:
        return {"checked": True, "replies_found": 0}

    results = []
    for reply in replies:
        lead = reply["lead"]
        body = reply["body"]

        # Classify
        classification = "neutral"
        if ai_configured():
            classification = await classify_reply(body)

        # Store reply in lead store
        lead_store.add_reply(lead["email"], body, classification)

        # Auto-respond if not unsubscribe or not_interested
        if classification in ("unsubscribe",):
            lead_store.mark_unsubscribed(lead["email"])
            results.append({"email": lead["email"], "action": "unsubscribed"})
            continue

        if classification in ("not_interested",):
            lead_store.mark_replied(lead["email"], "not_interested")
            results.append({"email": lead["email"], "action": "noted_not_interested"})
            continue

        # Generate response with AI
        if ai_configured():
            reply_body = await generate_reply(
                business_name=lead.get("name", "your business"),
                trade=lead.get("trade", "contractor"),
                city=lead.get("city", "your area"),
                state=lead.get("state", ""),
                reply_text=body,
                classification=classification,
            )
        else:
            reply_body = _default_reply(classification)

        if reply_body:
            result = await send_email(
                to_email=lead["email"],
                to_name=lead.get("name", "there").split()[0],
                subject=f"Re: {reply.get('subject', '')}",
                body_text=reply_body,
            )
            if result.get("success"):
                lead_store.mark_replied(lead["email"], f"responded_{classification}")
                results.append({"email": lead["email"], "action": f"responded_{classification}"})
            else:
                results.append({"email": lead["email"], "action": "send_failed", "error": result.get("error")})

    return {"checked": True, "replies_found": len(replies), "results": results}


def _default_reply(classification: str) -> str:
    replies = {
        "interested": "Glad you're interested! You can check out pricing and sign up here: https://owlbell.xyz/pricing. 30-day money-back guarantee — if you don't book more jobs, you don't pay. Let me know if you have any questions. — Mike",
        "question": "Happy to answer any questions! The short version: you forward your business number to us, we answer every call 24/7 in your business name, and you get a text with the details. $297/month. 30-day guarantee. More here: https://owlbell.xyz/pricing — Dave",
        "objection": "Totally fair concern. Here's the thing though — one extra job per year covers the cost. And with the 30-day guarantee, there's zero risk. If it doesn't bring in more calls, you don't pay. https://owlbell.xyz/pricing — Chris",
        "neutral": "Thanks for getting back to me. If you ever want to learn more about how Owlbell can help your business never miss another call, here's where to look: https://owlbell.xyz/pricing — Pat",
    }
    return replies.get(classification, replies["neutral"])
