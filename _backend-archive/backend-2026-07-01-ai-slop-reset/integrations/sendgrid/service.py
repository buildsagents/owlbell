from __future__ import annotations

from typing import Optional

import httpx
import structlog

from backend.config import get_settings

logger = structlog.get_logger(__name__)

SENDGRID_API_BASE = "https://api.sendgrid.com/v3"


def _api_key() -> Optional[str]:
    s = get_settings()
    key = s.integrations.sendgrid_api_key
    if key:
        if hasattr(key, "get_secret_value"):
            return key.get_secret_value()
        return str(key)
    return None


def is_configured() -> bool:
    return bool(_api_key())


def _from_email() -> str:
    s = get_settings()
    return s.integrations.sendgrid_from_email


def _from_name() -> str:
    s = get_settings()
    return s.integrations.sendgrid_from_name


async def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    content: str,
) -> dict:
    if not is_configured():
        return {"success": False, "error": "SendGrid not configured"}

    api_key = _api_key()
    payload = {
        "personalizations": [
            {
                "to": [{"email": to_email, "name": to_name}],
                "subject": subject,
            }
        ],
        "from": {"email": _from_email(), "name": _from_name()},
        "content": [{"type": "text/plain", "value": content}],
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{SENDGRID_API_BASE}/mail/send",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code not in (200, 201, 202):
            logger.warning("sendgrid.error", status=resp.status_code, body=resp.text[:300])
            return {"success": False, "error": f"SendGrid {resp.status_code}: {resp.text[:200]}"}

        logger.info("sendgrid.email_sent", to=to_email, subject=subject)
        return {"success": True}
    except Exception as exc:
        logger.error("sendgrid.error", to=to_email, error=str(exc))
        return {"success": False, "error": str(exc)}
