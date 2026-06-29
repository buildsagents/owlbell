"""Synchronous self-serve activation — provisions Retell or sandbox from intake."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)

# Inbound line callers dial to reach the AI (sandbox). NOT the owner's forward target.
SANDBOX_INBOUND_BASE = os.getenv("OWLBELL_SANDBOX_INBOUND_BASE", "+1888555")


@dataclass(frozen=True)
class ActivationResult:
    success: bool
    test_call_number: Optional[str] = None
    forward_number: Optional[str] = None
    retell_agent_id: Optional[str] = None
    provision_mode: str = "none"
    error: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "test_call_number": self.test_call_number,
            "forward_number": self.forward_number,
            "retell_agent_id": self.retell_agent_id,
            "provision_mode": self.provision_mode,
            "error": self.error,
        }


def normalize_phone(raw: str) -> Optional[str]:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) >= 10:
        return f"+{digits}"
    return None


def derive_sandbox_inbound_line(email: str) -> str:
    """Stable per-tenant inbound demo line where the AI answers."""
    h = int(hashlib.sha256(email.strip().lower().encode()).hexdigest()[:8], 16)
    suffix = f"{2000 + (h % 7999):04d}"
    base = re.sub(r"\D", "", SANDBOX_INBOUND_BASE)
    if len(base) >= 10:
        return f"+{base[:7]}{suffix}"
    return f"+1888555{suffix}"


def provision_sandbox_from_intake(intake: dict[str, Any]) -> dict[str, Any]:
    """Sandbox activation: validate owner forward line, provision distinct inbound AI line."""
    raw = (
        intake.get("forward_number")
        or intake.get("forwardNumber")
        or ""
    )
    forward = normalize_phone(str(raw))
    if not forward:
        return {"status": "failed", "error": "forward_number_required_for_activation"}

    email = str(intake.get("email") or "")
    if not email:
        return {"status": "failed", "error": "email_required_for_activation"}

    inbound = derive_sandbox_inbound_line(email)
    agent_slug = hashlib.sha256(email.encode()).hexdigest()[:12]
    return {
        "status": "complete",
        "retell_agent_id": f"sandbox_{agent_slug}",
        "retell_phone_number": inbound,
        "forward_number": forward,
        "sandbox": True,
        "provisioned_at": datetime.now(timezone.utc).isoformat(),
    }


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "business"
    return f"{base[:40]}-{uuid4().hex[:6]}"


async def ensure_self_serve_tenant(
    *,
    email: str,
    business_name: str,
    payload: dict[str, Any],
) -> UUID:
    from sqlalchemy import func, select

    from backend.db.models.tenant import Tenant
    from backend.domain.onboarding.intake_service import _require_session_maker

    sm = _require_session_maker()
    email_norm = email.strip().lower()
    forward = payload.get("forwardNumber") or payload.get("forward_number")

    async with sm() as db:
        row = await db.execute(
            select(Tenant.id).where(func.lower(Tenant.business_email) == email_norm)
        )
        existing = row.scalar_one_or_none()
        if existing:
            return existing

        tenant = Tenant(
            slug=_slugify(business_name),
            name=business_name,
            business_name=business_name,
            business_email=email_norm,
            business_phone=normalize_phone(str(forward or "")),
            industry=payload.get("trade") or payload.get("vertical"),
            greeting_message=payload.get("greeting"),
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        logger.info("onboarding.self_serve_tenant_created", tenant_id=str(tenant.id))
        return tenant.id


async def activate_self_serve(
    tenant_id: UUID,
    payload: dict[str, Any],
) -> ActivationResult:
    """Run sync provision (Retell when configured, else sandbox inbound AI line)."""
    from backend.integrations.retell.service import is_configured
    from backend.domain.onboarding.orchestrator import get_orchestrator
    from workers.onboarding_tasks import provision_retell_for_tenant

    tid = str(tenant_id)
    forward = normalize_phone(
        str(payload.get("forwardNumber") or payload.get("forward_number") or "")
    )
    try:
        if is_configured():
            result = await provision_retell_for_tenant(tid, intake_payload=payload)
            mode = "retell"
        else:
            result = provision_sandbox_from_intake(payload)
            mode = "sandbox"
            if result.get("status") == "complete":
                orch = get_orchestrator()
                await orch.on_provision_complete(tenant_id=tid, result=result)

        if result.get("status") != "complete":
            return ActivationResult(
                success=False,
                error=result.get("error", "provision_failed"),
                provision_mode=mode,
                forward_number=forward,
            )

        inbound = result.get("retell_phone_number")
        return ActivationResult(
            success=True,
            test_call_number=inbound,
            forward_number=result.get("forward_number") or forward,
            retell_agent_id=result.get("retell_agent_id"),
            provision_mode=mode,
        )
    except Exception as exc:
        logger.warning("onboarding.self_serve_activation_failed", tenant_id=tid, error=str(exc))
        return ActivationResult(success=False, error=str(exc), forward_number=forward)