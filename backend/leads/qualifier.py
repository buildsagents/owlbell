"""
leads/qualifier.py - Test if contractors answer their phones.

Uses Twilio to place a brief call to each contractor number,
detects whether a human answered or it went to voicemail,
and records the result.

Config-guarded: safely no-ops when Twilio not configured.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import structlog
import httpx

from backend.config import get_settings
from backend.integrations.twilio.service import is_configured as twilio_configured
from backend.integrations.twilio.service import _credentials, _request_with_retry

logger = structlog.get_logger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"

CALL_TIMEOUT_S = 12
CALLER_ID = "+14284361703"


async def test_contractor_phone(
    phone: str,
    business_name: str,
    webhook_base: Optional[str] = None,
) -> dict[str, Any]:
    """Call a contractor number and detect if it rings (no answer) or connects.

    Uses Twilio's status callback to determine call outcome:
    - "completed" = someone answered (or machine detected and call went through)
    - "no-answer" / "busy" / "failed" = didn't get through
    - "ringing" (timeout) = rang indefinitely
    """
    if not twilio_configured():
        return {"success": False, "phone": phone, "answered": None, "error": "Twilio not configured"}

    creds = _credentials()
    if not creds:
        return {"success": False, "phone": phone, "answered": None, "error": "No credentials"}
    sid, token = creds

    twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="alice">Sorry, wrong number.</Say><Hangup/></Response>'

    url = f"{TWILIO_API_BASE}/Accounts/{sid}/Calls.json"
    data = {
        "To": phone,
        "From": CALLER_ID,
        "Twiml": twiml,
        "Timeout": CALL_TIMEOUT_S,
        "StatusCallback": webhook_base or "",
        "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
    }

    try:
        resp = await _request_with_retry("POST", url, auth=(sid, token), data=data)
        if resp.status_code not in (200, 201):
            return {"success": False, "phone": phone, "answered": None, "error": f"Twilio {resp.status_code}: {resp.text[:200]}"}

        call = resp.json()
        call_sid = call.get("sid")
        status = call.get("status", "")

        answered = status in ("completed", "in-progress", "answered")

        return {
            "success": True,
            "phone": phone,
            "business_name": business_name,
            "call_sid": call_sid,
            "status": status,
            "answered": answered,
        }
    except Exception as exc:
        logger.error("qualifier.call_error", phone=phone, error=str(exc))
        return {"success": False, "phone": phone, "answered": None, "error": str(exc)}


async def qualify_leads(
    leads: list[dict[str, Any]],
    webhook_base: Optional[str] = None,
    max_concurrent: int = 3,
) -> list[dict[str, Any]]:
    """Test a batch of leads for phone answerability.

    Returns leads with qualification data appended.
    Only processes leads that have a phone number.
    """
    qualified = []

    for i in range(0, len(leads), max_concurrent):
        batch = leads[i:i + max_concurrent]
        tasks = []

        for lead in batch:
            if not lead.get("phone"):
                lead["qualified"] = False
                lead["qualification_error"] = "No phone number"
                qualified.append(lead)
                continue

            tasks.append(test_contractor_phone(
                phone=lead["phone"],
                business_name=lead.get("name", ""),
                webhook_base=webhook_base,
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for lead, result in zip(batch, results):
            if isinstance(result, Exception):
                lead["qualified"] = False
                lead["qualification_error"] = str(result)
            elif result.get("success"):
                lead["call_sid"] = result.get("call_sid")
                lead["call_status"] = result.get("status")
                lead["qualified"] = True
                lead["misses_calls"] = not result.get("answered", False)
            else:
                lead["qualified"] = False
                lead["qualification_error"] = result.get("error", "Unknown")

            qualified.append(lead)

        if i + max_concurrent < len(leads):
            await asyncio.sleep(0.5)

    return qualified
