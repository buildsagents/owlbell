"""api/routes/phone_numbers.py - Phone number provisioning routes.

Endpoints:
    GET    /phone-numbers/available — list available numbers from Twilio
    POST   /phone-numbers/assign   — buy & assign a number to tenant
    GET    /phone-numbers          — list numbers assigned to current tenant
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentUser, DBSession, RequireAdmin, UserContext
from backend.db.models.tenant import TenantConfig
from backend.integrations.retell.service import import_twilio_number, is_configured as retell_is_configured
from backend.integrations.twilio.service import (
    buy_number,
    get_termination_uri,
    is_configured as twilio_is_configured,
    list_available_numbers,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/phone-numbers", tags=["Phone Numbers"])

_PHONE_KEY = "assigned_phone"
_TWILIO_SID_KEY = "twilio_phone_sid"


async def _get_or_create_tenant_config(db: AsyncSession, tenant_id: uuid.UUID) -> TenantConfig:
    result = await db.execute(select(TenantConfig).where(TenantConfig.tenant_id == tenant_id))
    cfg = result.scalar_one_or_none()
    if cfg is None:
        cfg = TenantConfig(tenant_id=tenant_id)
        db.add(cfg)
        await db.flush()
    return cfg


def _phone_from_integrations(integrations: dict) -> Optional[str]:
    return integrations.get(_PHONE_KEY)


@router.get("/available")
async def get_available_numbers(
    area_code: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    _user: UserContext = CurrentUser,
) -> dict[str, Any]:
    """List available phone numbers from Twilio.

    Falls back to an empty list if Twilio is not configured.
    """
    numbers = await list_available_numbers(area_code=area_code, limit=limit)

    data = [
        {
            "phone_number": n.get("phone_number"),
            "friendly": n.get("friendly"),
            "locality": n.get("locality"),
            "region": n.get("region"),
            "capabilities": n.get("capabilities", {}),
            "monthly_price": n.get("monthly_price"),
            "setup_price": n.get("setup_price"),
        }
        for n in numbers
    ]
    return {"success": True, "data": data}


@router.post("/assign", status_code=status.HTTP_201_CREATED)
async def assign_phone_number(
    phone_number: str,
    user: UserContext = RequireAdmin,
    db: AsyncSession = DBSession,
) -> dict[str, Any]:
    """Buy a phone number from Twilio and import it into Retell AI.

    Stores the assignment in TenantConfig.integrations JSONB.
    Requires both Twilio and Retell to be configured.
    """
    if not twilio_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twilio is not configured. Set INTEGRATION_TWILIO_ACCOUNT_SID and INTEGRATION_TWILIO_AUTH_TOKEN.",
        )

    termination_uri = get_termination_uri()
    if not termination_uri and retell_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twilio SIP trunk not configured. Set INTEGRATION_TWILIO_SIP_TRUNK_TERMINATION_URI.",
        )

    cfg = await _get_or_create_tenant_config(db, user.tenant_id)
    integrations = dict(cfg.integrations or {})
    if _phone_from_integrations(integrations):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant already has a phone number assigned",
        )

    buy_result = await buy_number(
        phone_number=phone_number,
        friendly_name=f"Owlbell - {str(user.tenant_id)[:8]}",
    )
    if not buy_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to buy number from Twilio: {buy_result.get('error', 'unknown error')}",
        )

    if retell_is_configured() and termination_uri:
        import_result = import_twilio_number(
            phone_number=phone_number,
            termination_uri=termination_uri,
            nickname=f"Owlbell - {str(user.tenant_id)[:8]}",
        )
        if import_result.get("success"):
            logger.info(
                "phone_numbers.imported_to_retell",
                phone_number=phone_number,
            )
        else:
            logger.warning(
                "phone_numbers.retell_import_failed",
                phone_number=phone_number,
                error=import_result.get("error"),
            )

    twilio_sid = buy_result.get("sid")
    integrations[_PHONE_KEY] = phone_number
    if twilio_sid:
        integrations[_TWILIO_SID_KEY] = twilio_sid
    integrations["assigned_at"] = datetime.now(timezone.utc).isoformat()
    cfg.integrations = integrations

    logger.info(
        "phone_numbers.assigned",
        tenant_id=str(user.tenant_id),
        phone_number=phone_number,
        twilio_sid=twilio_sid,
    )
    return {
        "success": True,
        "data": {
            "tenant_id": str(user.tenant_id),
            "phone_number": phone_number,
            "twilio_sid": twilio_sid,
            "assigned_at": integrations["assigned_at"],
        },
    }


@router.get("")
async def list_assigned_numbers(
    user: UserContext = CurrentUser,
    db: AsyncSession = DBSession,
) -> dict[str, Any]:
    """List phone numbers assigned to the current tenant."""
    result = await db.execute(select(TenantConfig).where(TenantConfig.tenant_id == user.tenant_id))
    cfg = result.scalar_one_or_none()
    integrations = dict(cfg.integrations or {}) if cfg else {}
    phone = _phone_from_integrations(integrations)
    if not phone:
        return {"success": True, "data": []}

    numbers = [
        {
            "id": str(cfg.id) if cfg else str(uuid.uuid4()),
            "phone_number": phone,
            "assigned_at": integrations.get("assigned_at", datetime.now(timezone.utc).isoformat()),
            "capabilities": {"voice": True, "sms": True},
        }
    ]

    return {"success": True, "data": numbers}