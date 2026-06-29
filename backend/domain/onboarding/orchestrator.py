"""domain/onboarding/orchestrator.py - Unified onboarding state machine.

Coordinates:
  checkout_completed -> welcome_email -> (await intake) -> retell provision -> pipeline steps

Self-serve and agency clients share the same ``OnboardingPipelineRecord``.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import structlog

from backend.domain.onboarding.steps import (
    STEP_INTAKE_SUBMITTED,
    STEP_PAYMENT_RECEIVED,
    STEP_PHONE_PROVISIONED,
    STEP_RETELL_PROVISIONED,
)
from backend.operations.onboarding import automation, email_sequence

logger = structlog.get_logger(__name__)

_orchestrator: Optional["OnboardingOrchestrator"] = None


class OnboardingOrchestrator:
    """Single entry point for onboarding lifecycle events."""

    def __init__(self, session_maker: Callable[[], Any]):
        self._session_maker = session_maker

    async def on_checkout_completed(
        self,
        *,
        tenant_id: str,
        email: str,
        business_name: str,
        contact_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """Stripe checkout.session.completed — create pipeline and mark payment received."""
        sm = self._session_maker
        existing = await automation.get_pipeline(sm, tenant_id)
        if existing is None:
            pipeline = await automation.create_pipeline(
                sm,
                tenant_id=tenant_id,
                tenant_name=business_name,
                tenant_email=email,
            )
            await email_sequence.create_sequence(
                sm,
                tenant_id=tenant_id,
                contact_name=contact_name or business_name,
                business_name=business_name,
                contact_email=email,
                pipeline_id=pipeline.id,
            )
        await automation.complete_step(
            sm, tenant_id, STEP_PAYMENT_RECEIVED,
            notes="Payment received via Stripe checkout",
        )
        logger.info("onboarding.checkout_completed", tenant_id=tenant_id)
        return {"pipeline_created": existing is None, "step": STEP_PAYMENT_RECEIVED}

    async def on_intake_submitted(
        self,
        *,
        tenant_id: str,
        intake_payload: Optional[dict[str, Any]] = None,
        notes: str = "Submitted via onboarding portal",
    ) -> dict[str, Any]:
        """Post-checkout intake — complete intake step and enqueue Retell provisioning."""
        sm = self._session_maker
        pipeline = await automation.get_pipeline(sm, tenant_id)
        if pipeline is None:
            email = (intake_payload or {}).get("email", "")
            name = (intake_payload or {}).get("business_name", "Client")
            await self.on_checkout_completed(
                tenant_id=tenant_id,
                email=email,
                business_name=name,
            )

        result = await automation.complete_step(
            sm, tenant_id, STEP_INTAKE_SUBMITTED, notes=notes,
        )
        provision_scheduled = False
        if result.get("success"):
            provision_scheduled = self._schedule_provision(tenant_id, intake_payload)

        return {
            **result,
            "provision_scheduled": provision_scheduled,
        }

    async def on_provision_complete(
        self,
        *,
        tenant_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Called after Retell provisioning succeeds — advance AI + phone steps."""
        sm = self._session_maker
        if result.get("status") != "complete":
            await automation.block_step(
                sm, tenant_id, STEP_RETELL_PROVISIONED,
                reason=result.get("error", "Retell provisioning failed"),
            )
            return {"success": False, "error": result.get("error")}

        ai_result = await automation.complete_step(
            sm, tenant_id, STEP_RETELL_PROVISIONED,
            notes=f"Retell agent {result.get('retell_agent_id')}",
        )
        phone_result = await automation.complete_step(
            sm, tenant_id, STEP_PHONE_PROVISIONED,
            notes=f"Phone {result.get('retell_phone_number')}",
        )
        return {
            "success": True,
            "ai_configuration": ai_result,
            "phone_setup": phone_result,
        }

    async def complete_step(
        self,
        tenant_id: str,
        step_id: str,
        *,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        """Agency/manual step completion."""
        return await automation.complete_step(
            self._session_maker, tenant_id, step_id, notes=notes,
        )

    async def get_status(self, tenant_id: str) -> Optional[dict[str, Any]]:
        pipeline = await automation.get_pipeline(self._session_maker, tenant_id)
        return pipeline.get_status() if pipeline else None

    async def get_status_by_email(self, email: str) -> Optional[dict[str, Any]]:
        from sqlalchemy import func, select

        from backend.db.models.tenant import Tenant
        from backend.db.models.user import User

        email_norm = email.strip().lower()
        async with self._session_maker() as db:
            row = await db.execute(
                select(Tenant.id).where(func.lower(Tenant.business_email) == email_norm)
            )
            tid = row.scalar_one_or_none()
            if not tid:
                row = await db.execute(
                    select(User.tenant_id).where(func.lower(User.email) == email_norm)
                )
                tid = row.scalar_one_or_none()
        if not tid:
            return None
        return await self.get_status(str(tid))

    def _schedule_provision(
        self, tenant_id: str, intake_payload: Optional[dict[str, Any]],
    ) -> bool:
        try:
            from workers.onboarding_tasks import schedule_provision_retell

            schedule_provision_retell(tenant_id, intake_payload=intake_payload)
            return True
        except Exception as exc:
            logger.error("onboarding.provision_schedule_failed", tenant_id=tenant_id, error=str(exc))
            return False


def get_orchestrator() -> OnboardingOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        from backend.db.session import require_session_maker

        _orchestrator = OnboardingOrchestrator(require_session_maker())
    return _orchestrator