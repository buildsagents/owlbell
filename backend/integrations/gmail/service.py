from __future__ import annotations

import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx
import structlog

from backend.config import get_settings

logger = structlog.get_logger(__name__)

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def _config():
    s = get_settings()
    cfg = s.integrations
    secret = cfg.gmail_client_secret
    refresh = cfg.gmail_refresh_token
    if secret and hasattr(secret, "get_secret_value"):
        secret = secret.get_secret_value()
    if refresh and hasattr(refresh, "get_secret_value"):
        refresh = refresh.get_secret_value()
    return {
        "client_id": cfg.gmail_client_id,
        "client_secret": secret,
        "refresh_token": refresh,
        "from_email": cfg.gmail_from_email,
        "from_name": cfg.gmail_from_name,
    }


def is_configured() -> bool:
    c = _config()
    return bool(c["client_id"] and c["client_secret"] and c["refresh_token"])


async def _get_access_token() -> Optional[str]:
    c = _config()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": c["client_id"],
                "client_secret": c["client_secret"],
                "refresh_token": c["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code != 200:
        logger.error("gmail.token_error", status=resp.status_code, body=resp.text[:200])
        return None
    return resp.json().get("access_token")


def _build_rfc2822(
    to_email: str,
    to_name: str,
    subject: str,
    body_text: str,
    from_email: str,
    from_name: str,
) -> str:
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = f"{to_name} <{to_email}>"
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    return msg.as_string()


async def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    body_text: str,
) -> dict:
    if not is_configured():
        return {"success": False, "error": "Gmail API not configured"}

    c = _config()
    access_token = await _get_access_token()
    if not access_token:
        return {"success": False, "error": "Failed to get Gmail access token"}

    raw = _build_rfc2822(to_email, to_name, subject, body_text, c["from_email"], c["from_name"])
    encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{GMAIL_API_BASE}/users/me/messages/send",
                json={"raw": encoded},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code not in (200, 201, 202):
            logger.warning("gmail.send_error", status=resp.status_code, body=resp.text[:300])
            return {"success": False, "error": f"Gmail API {resp.status_code}: {resp.text[:200]}"}
        logger.info("gmail.email_sent", to=to_email, subject=subject)
        return {"success": True}
    except Exception as exc:
        logger.error("gmail.send_error", to=to_email, error=str(exc))
        return {"success": False, "error": str(exc)}
