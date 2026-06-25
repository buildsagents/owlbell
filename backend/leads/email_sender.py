from __future__ import annotations

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import structlog

from backend.config import get_settings
from backend.integrations.sendgrid.service import send_email as sendgrid_send
from backend.integrations.sendgrid.service import is_configured as sendgrid_configured

logger = structlog.get_logger(__name__)


def _smtp_config():
    s = get_settings()
    cfg = s.integrations
    password = cfg.smtp_password
    if hasattr(password, "get_secret_value"):
        password = password.get_secret_value()
    return {
        "host": cfg.smtp_host,
        "port": cfg.smtp_port,
        "username": cfg.smtp_username,
        "password": password,
        "from_email": cfg.smtp_from_email,
        "from_name": cfg.smtp_from_name,
    }


def is_configured() -> bool:
    if sendgrid_configured():
        return True
    cfg = _smtp_config()
    return bool(cfg["username"] and cfg["password"])


def _build_message(
    to_email: str,
    to_name: str,
    subject: str,
    body_text: str,
    reply_to: Optional[str] = None,
) -> str:
    msg = MIMEMultipart("alternative")
    cfg = _smtp_config()
    msg["From"] = f"{cfg['from_name']} <{cfg['from_email']}>"
    msg["To"] = f"{to_name} <{to_email}>"
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    return msg.as_string()


async def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    body_text: str,
    reply_to: Optional[str] = None,
) -> dict:
    # Prefer SendGrid (REST API on port 443, works from Railway)
    if sendgrid_configured():
        logger.info("email.send_via_sendgrid", to=to_email, subject=subject)
        return await sendgrid_send(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            content=body_text,
        )

    # Fall back to SMTP (works locally, blocked on Railway)
    if not _smtp_config()["username"] or not _smtp_config()["password"]:
        return {"success": False, "error": "No email provider configured (set SendGrid API key or SMTP credentials)"}

    cfg = _smtp_config()
    raw_message = _build_message(to_email, to_name, subject, body_text, reply_to)

    def _send():
        if cfg["port"] == 465:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15) as server:
                server.login(cfg["username"], cfg["password"])
                server.sendmail(cfg["from_email"], [to_email], raw_message)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
                server.starttls()
                server.login(cfg["username"], cfg["password"])
                server.sendmail(cfg["from_email"], [to_email], raw_message)

    try:
        await asyncio.to_thread(_send)
        logger.info("email.sent_via_smtp", to=to_email, subject=subject)
        return {"success": True}
    except smtplib.SMTPAuthenticationError:
        logger.error("email.auth_error", hint="Check INTEGRATION_SMTP_USERNAME and INTEGRATION_SMTP_PASSWORD. For Gmail, use an App Password.")
        return {"success": False, "error": "SMTP authentication failed"}
    except Exception as exc:
        logger.error("email.send_error", to=to_email, error=str(exc))
        return {"success": False, "error": str(exc)}
