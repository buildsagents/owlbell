"""integrations/twilio/service.py - Twilio phone number provisioning.

Manages phone number purchasing, listing, and release via the Twilio REST API.
Numbers bought here are imported into Retell AI (via integrations/retell/service.py)
so Retell can answer calls with AI agents.

Config-guarded: all operations silently return empty/false when Twilio
credentials are not configured, safe to run in dev/CI.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any, Optional

import structlog
import httpx

from backend.config import get_settings

logger = structlog.get_logger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"
TWILIO_TRUNKING_BASE = "https://trunking.twilio.com/v1"

MAX_RETRIES = 3
BASE_DELAY_S = 1.0
MAX_DELAY_S = 8.0


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------


def _idempotency_key(func: str, **kwargs) -> str:
    """Deterministic idempotency key from function name + sorted kwargs."""
    raw = f"{func}:{json.dumps(kwargs, sort_keys=True, default=str)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


async def _request_with_retry(
    method: str,
    url: str,
    *,
    auth: tuple[str, str],
    data: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: float = 15.0,
    idempotent: bool = False,
    idempotency_key: Optional[str] = None,
) -> httpx.Response:
    """Make an HTTP request with exponential backoff retry.

    For idempotent mutations (buy_number, assign_to_trunk) retries on
    5xx / network errors. GET requests are always retried.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                req = client.build_request(method, url, auth=auth, data=data, params=params)
                if idempotency_key:
                    req.headers["Idempotency-Key"] = idempotency_key
                resp = await client.send(req)

            if resp.status_code < 500 or attempt == MAX_RETRIES:
                return resp

            logger.warning(
                "twilio.retry",
                url=url, status=resp.status_code, attempt=attempt,
            )
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            if attempt == MAX_RETRIES:
                raise
            logger.warning("twilio.retry_error", url=url, error=str(exc), attempt=attempt)

        await asyncio.sleep(min(BASE_DELAY_S * (2 ** attempt), MAX_DELAY_S))

    raise last_exc or RuntimeError("Unreachable")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def is_configured() -> bool:
    """True when Twilio account SID and auth token are both present."""
    integrations = get_settings().integrations
    return bool(integrations.twilio_account_sid and integrations.twilio_auth_token)


def get_termination_uri() -> Optional[str]:
    """Return the configured Twilio Elastic SIP Trunk termination URI."""
    return get_settings().integrations.twilio_sip_trunk_termination_uri


def get_trunk_sid() -> Optional[str]:
    """Return the configured Twilio Elastic SIP Trunk SID."""
    return get_settings().integrations.twilio_sip_trunk_sid


def _credentials() -> Optional[tuple[str, str]]:
    integrations = get_settings().integrations
    sid = (
        integrations.twilio_account_sid.get_secret_value()
        if integrations.twilio_account_sid else None
    )
    token = (
        integrations.twilio_auth_token.get_secret_value()
        if integrations.twilio_auth_token else None
    )
    if sid and token:
        return sid, token
    return None


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


async def assign_number_to_trunk(phone_sid: str) -> dict[str, Any]:
    """Assign an incoming phone number to the Elastic SIP Trunk.

    Uses the Twilio Trunking API so the trunk can route inbound calls to Retell AI.
    """
    if not is_configured():
        return {"success": False, "error": "Twilio not configured"}

    trunk_sid = get_trunk_sid()
    if not trunk_sid:
        return {"success": False, "error": "Twilio SIP Trunk SID not configured"}

    creds = _credentials()
    if not creds:
        return {"success": False, "error": "Twilio not configured"}
    sid, token = creds

    url = f"{TWILIO_TRUNKING_BASE}/Trunks/{trunk_sid}/PhoneNumbers"
    data = {"PhoneNumberSid": phone_sid}

    try:
        resp = await _request_with_retry(
            "POST", url, auth=(sid, token), data=data,
            idempotent=True, idempotency_key=_idempotency_key("assign_to_trunk", phone_sid=phone_sid),
        )
        if resp.status_code not in (200, 201):
            return {"success": False, "error": f"Twilio Trunking {resp.status_code}: {resp.text[:200]}"}
        payload = resp.json()
        logger.info("twilio.number_assigned_to_trunk", phone_sid=phone_sid, trunk_sid=trunk_sid)
        return {"success": True, "sid": payload.get("sid")}
    except Exception as exc:
        logger.error("twilio.assign_to_trunk_error", phone_sid=phone_sid, error=str(exc))
        return {"success": False, "error": str(exc)}


async def list_available_numbers(
    area_code: Optional[str] = None,
    limit: int = 10,
    country: str = "US",
) -> list[dict[str, Any]]:
    """Search for available phone numbers on Twilio."""
    if not is_configured():
        return []

    creds = _credentials()
    if not creds:
        return []
    sid, token = creds
    url = f"{TWILIO_API_BASE}/Accounts/{sid}/AvailablePhoneNumbers/{country}/Local.json"

    params: dict[str, Any] = {"Limit": min(limit, 50)}
    if area_code:
        params["AreaCode"] = area_code

    try:
        resp = await _request_with_retry("GET", url, auth=(sid, token), params=params)
        if resp.status_code != 200:
            logger.warning("twilio.list_numbers_failed", status=resp.status_code, body=resp.text[:200])
            return []
        payload = resp.json()
        return [
            {
                "phone_number": n.get("phone_number"),
                "friendly": n.get("friendly_name"),
                "locality": n.get("locality"),
                "region": n.get("region"),
                "capabilities": {
                    "voice": n.get("capabilities", {}).get("voice", False),
                    "sms": n.get("capabilities", {}).get("sms", False),
                    "mms": n.get("capabilities", {}).get("mms", False),
                },
                "monthly_price": n.get("monthly_price"),
                "setup_price": n.get("setup_price"),
            }
            for n in payload.get("available_phone_numbers", [])
        ]
    except Exception as exc:
        logger.warning("twilio.list_numbers_error", error=str(exc))
        return []


async def buy_number(
    phone_number: str,
    friendly_name: Optional[str] = None,
) -> dict[str, Any]:
    """Purchase a specific phone number from Twilio.

    Returns the purchased number details including the Twilio SID, or an error dict.
    Uses idempotency key so retrying is safe.
    """
    if not is_configured():
        return {"success": False, "error": "Twilio not configured"}

    creds = _credentials()
    if not creds:
        return {"success": False, "error": "Twilio not configured"}
    sid, token = creds

    url = f"{TWILIO_API_BASE}/Accounts/{sid}/IncomingPhoneNumbers.json"
    data: dict[str, Any] = {"PhoneNumber": phone_number}
    if friendly_name:
        data["FriendlyName"] = friendly_name

    try:
        resp = await _request_with_retry(
            "POST", url, auth=(sid, token), data=data,
            idempotent=True, idempotency_key=_idempotency_key("buy_number", phone_number=phone_number),
        )
        if resp.status_code not in (200, 201):
            return {"success": False, "error": f"Twilio {resp.status_code}: {resp.text[:200]}"}
        payload = resp.json()
        logger.info("twilio.number_bought", phone_number=phone_number, sid=payload.get("sid"))
        return {
            "success": True,
            "sid": payload.get("sid"),
            "phone_number": payload.get("phone_number"),
            "friendly_name": payload.get("friendly_name"),
            "capabilities": payload.get("capabilities", {}),
        }
    except Exception as exc:
        logger.error("twilio.buy_number_error", phone_number=phone_number, error=str(exc))
        return {"success": False, "error": str(exc)}


async def release_number(phone_number_sid: str) -> dict[str, Any]:
    """Release / delete a phone number from Twilio."""
    if not is_configured():
        return {"success": False, "error": "Twilio not configured"}

    creds = _credentials()
    if not creds:
        return {"success": False, "error": "Twilio not configured"}
    sid, token = creds

    url = f"{TWILIO_API_BASE}/Accounts/{sid}/IncomingPhoneNumbers/{phone_number_sid}.json"

    try:
        resp = await _request_with_retry("DELETE", url, auth=(sid, token))
        if resp.status_code not in (200, 204):
            return {"success": False, "error": f"Twilio {resp.status_code}: {resp.text[:200]}"}
        logger.info("twilio.number_released", sid=phone_number_sid)
        return {"success": True}
    except Exception as exc:
        logger.error("twilio.release_number_error", sid=phone_number_sid, error=str(exc))
        return {"success": False, "error": str(exc)}
