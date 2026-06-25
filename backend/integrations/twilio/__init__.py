"""integrations/twilio - SMS delivery and emergency alerts via Twilio.

Config-guarded: SMS is only actually sent over the Twilio REST API when
``INTEGRATION_TWILIO_ACCOUNT_SID`` / ``..._AUTH_TOKEN`` / ``..._FROM_NUMBER``
are configured. Without credentials the message is logged and returned with
``status="skipped"`` so nothing is sent — safe to run in dev/CI.

Every send is recorded in ``notification_logs`` when a tenant id and session
maker are supplied.

Public API:
    is_configured() -> bool
    await send_sms(to, body, ...)            -> dict
    await send_emergency_alert(...)          -> dict
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Callable, Optional

import structlog

from backend.config import get_settings

logger = structlog.get_logger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


def is_configured() -> bool:
    """True when Twilio credentials and a from-number are all present."""
    integrations = get_settings().integrations
    return bool(
        integrations.twilio_account_sid
        and integrations.twilio_auth_token
        and integrations.twilio_from_number
    )


def _credentials() -> tuple[Optional[str], Optional[str], Optional[str]]:
    integrations = get_settings().integrations
    sid = (
        integrations.twilio_account_sid.get_secret_value()
        if integrations.twilio_account_sid else None
    )
    token = (
        integrations.twilio_auth_token.get_secret_value()
        if integrations.twilio_auth_token else None
    )
    return sid, token, integrations.twilio_from_number


async def _deliver_via_twilio(to: str, body: str) -> dict[str, Any]:
    """POST a message to the Twilio REST API. Assumes creds are configured."""
    import httpx

    sid, token, from_number = _credentials()
    url = f"{TWILIO_API_BASE}/Accounts/{sid}/Messages.json"
    data = {"To": to, "From": from_number, "Body": body}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, data=data, auth=(sid, token))

    if resp.status_code in (200, 201):
        payload = resp.json()
        return {
            "success": True,
            "status": "sent",
            "provider_message_id": payload.get("sid"),
        }
    return {
        "success": False,
        "status": "failed",
        "error": f"twilio {resp.status_code}: {resp.text[:200]}",
    }


async def _log_notification(
    session_maker: Callable[[], Any],
    tenant_id: uuid.UUID,
    recipient: str,
    body: str,
    result: dict[str, Any],
    event_type: Optional[str],
    entity_id: Optional[uuid.UUID],
) -> None:
    """Persist a notification_logs row for an SMS send (best-effort)."""
    try:
        from backend.db.models.business import NotificationLog
        from backend.db.models.enums import NotificationChannel

        async with session_maker() as session:
            row = NotificationLog(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                channel=NotificationChannel.SMS,
                recipient=recipient,
                content=body,
                event_type=event_type,
                entity_type="call" if entity_id else None,
                entity_id=entity_id,
                status=result.get("status", "pending"),
                error_message=result.get("error"),
                provider_message_id=result.get("provider_message_id"),
                delivered_at=datetime.utcnow() if result.get("success") else None,
            )
            session.add(row)
            await session.commit()
    except Exception as exc:  # logging must never break the send path
        logger.warning("twilio.notification_log_failed", error=str(exc))


async def send_sms(
    to: str,
    body: str,
    *,
    tenant_id: Optional[uuid.UUID] = None,
    session_maker: Optional[Callable[[], Any]] = None,
    event_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
) -> dict[str, Any]:
    """Send an SMS via Twilio (config-guarded).

    Returns a dict with ``success``, ``status`` ('sent' | 'failed' | 'skipped'),
    and ``provider_message_id`` / ``error`` as applicable. When ``tenant_id``
    and ``session_maker`` are given, the attempt is recorded in
    ``notification_logs``.
    """
    if not to or not body:
        return {"success": False, "status": "failed", "error": "to and body are required"}

    if not is_configured():
        logger.info("twilio.sms_skipped_no_config", to=to, body_preview=body[:60])
        result = {
            "success": True,
            "status": "skipped",
            "note": "Twilio not configured; SMS logged but not sent",
        }
    else:
        try:
            result = await _deliver_via_twilio(to, body)
            logger.info("twilio.sms_sent", to=to, status=result.get("status"))
        except Exception as exc:
            logger.error("twilio.sms_error", to=to, error=str(exc))
            result = {"success": False, "status": "failed", "error": str(exc)}

    if tenant_id is not None and session_maker is not None:
        await _log_notification(
            session_maker, tenant_id, to, body, result, event_type, entity_id
        )

    return result


async def _resolve_emergency_number(
    session_maker: Callable[[], Any], tenant_id: uuid.UUID
) -> Optional[str]:
    """Find the tenant's emergency contact number from tenant config / phone."""
    from sqlalchemy import select

    from backend.db.models.tenant import Tenant, TenantConfig

    async with session_maker() as session:
        cfg = await session.execute(
            select(TenantConfig.value).where(
                TenantConfig.tenant_id == tenant_id,
                TenantConfig.key.in_(
                    ("emergency_transfer_number", "emergency_number", "owner_phone")
                ),
            )
        )
        for value in cfg.scalars().all():
            if value:
                return value
        tenant = (
            await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one_or_none()
        if tenant is not None:
            return getattr(tenant, "business_phone", None)
    return None


async def send_emergency_alert(
    tenant_id: uuid.UUID,
    *,
    session_maker: Optional[Callable[[], Any]] = None,
    to_number: Optional[str] = None,
    caller_number: str = "",
    reason: str = "",
    business_name: str = "",
    call_id: Optional[uuid.UUID] = None,
) -> dict[str, Any]:
    """Send an emergency SMS alert to the tenant's emergency contact.

    The destination is ``to_number`` if given, otherwise resolved from the
    tenant's configured emergency number. Config-guarded like ``send_sms``.
    """
    recipient = to_number
    if not recipient and session_maker is not None:
        recipient = await _resolve_emergency_number(session_maker, tenant_id)

    if not recipient:
        logger.warning("twilio.emergency_no_recipient", tenant_id=str(tenant_id))
        return {"success": False, "status": "failed", "error": "No emergency number configured"}

    name = business_name or "your business"
    body = (
        f"🚨 EMERGENCY at {name}: caller {caller_number or 'unknown'} flagged an "
        f"urgent issue. {reason}".strip()
    )

    return await send_sms(
        recipient,
        body,
        tenant_id=tenant_id,
        session_maker=session_maker,
        event_type="call.emergency",
        entity_id=call_id,
    )
