"""Onboarding intake persistence and post-store pipeline — isolated from HTTP layer."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select

logger = logging.getLogger(__name__)


class IntakeDatabaseError(RuntimeError):
    """DB unavailable for intake — HTTP layer maps to 503."""


class DatabaseNotReadyError(IntakeDatabaseError):
    """Raised when the async session factory is unavailable."""


@dataclass(frozen=True)
class IntakeStoreResult:
    stored: bool
    intake_id: str
    tenant_id: Optional[UUID]
    email: str
    business_name: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class PipelineResult:
    success: bool = False
    provision_scheduled: bool = False
    error: Optional[str] = None
    activated: bool = False
    test_call_number: Optional[str] = None
    forward_number: Optional[str] = None
    retell_agent_id: Optional[str] = None
    provision_mode: Optional[str] = None

    @classmethod
    def from_orchestrator(cls, orch_result: dict[str, Any]) -> PipelineResult:
        return cls(
            success=bool(orch_result.get("success")),
            provision_scheduled=bool(orch_result.get("provision_scheduled")),
        )

    @classmethod
    def failed(cls, error: str) -> PipelineResult:
        return cls(error=error)


def _require_session_maker():
    from backend.db.session import require_session_maker

    try:
        return require_session_maker()
    except RuntimeError as exc:
        raise DatabaseNotReadyError(str(exc)) from exc


async def _find_tenant_id_by_email(db, email: str) -> Optional[UUID]:
    from backend.db.models.tenant import Tenant
    from backend.db.models.user import User

    email_norm = email.strip().lower()
    if not email_norm:
        return None

    row = await db.execute(
        select(Tenant.id).where(func.lower(Tenant.business_email) == email_norm)
    )
    tid = row.scalar_one_or_none()
    if tid:
        return tid

    row = await db.execute(
        select(User.tenant_id).where(func.lower(User.email) == email_norm)
    )
    return row.scalar_one_or_none()


async def persist_intake(
    *,
    email: str,
    business_name: str,
    session_id: Optional[str],
    payload: dict[str, Any],
) -> IntakeStoreResult:
    """Persist intake row and commit. Raises IntakeDatabaseError when DB is unavailable."""
    from backend.db.models.onboarding import OnboardingIntakeRecord

    try:
        sm = _require_session_maker()
        async with sm() as db:
            tenant_id = await _find_tenant_id_by_email(db, email)
            record = OnboardingIntakeRecord(
                tenant_id=tenant_id,
                email=email,
                business_name=business_name,
                stripe_session_id=session_id,
                payload_json=payload,
                status="linked" if tenant_id else "submitted",
            )
            db.add(record)
            await db.commit()
            await db.refresh(record)
            return IntakeStoreResult(
                stored=True,
                intake_id=str(record.id),
                tenant_id=tenant_id,
                email=email,
                business_name=business_name,
                payload=payload,
            )
    except IntakeDatabaseError:
        raise
    except Exception as exc:
        logger.warning(
            "onboarding.persist_intake_failed type=%s error=%s",
            type(exc).__name__,
            exc,
        )
        raise IntakeDatabaseError(str(exc)) from exc


async def run_pipeline_after_store(
    tenant_id: Optional[UUID],
    payload: dict[str, Any],
) -> PipelineResult:
    """Advance onboarding pipeline after intake is stored. Never raises."""
    self_serve = bool(payload.get("self_serve") or payload.get("selfServe"))

    try:
        if self_serve:
            from backend.integrations.retell.service import is_configured
            from backend.domain.onboarding.self_serve_pipeline import (
                execute_self_serve_activation,
                pipeline_result_from_response,
            )

            if not is_configured():
                response = execute_self_serve_activation(payload)
                return pipeline_result_from_response(response)

            from backend.domain.onboarding.activation_service import (
                activate_self_serve,
                ensure_self_serve_tenant,
            )

            email = str(payload.get("email") or "")
            business_name = str(
                payload.get("business_name") or payload.get("businessName") or "Business"
            )
            tid = tenant_id or await ensure_self_serve_tenant(
                email=email,
                business_name=business_name,
                payload=payload,
            )
            activation = await activate_self_serve(tid, payload)
            if activation.success:
                return PipelineResult(
                    success=True,
                    provision_scheduled=False,
                    activated=True,
                    test_call_number=activation.test_call_number,
                    forward_number=activation.forward_number,
                    retell_agent_id=activation.retell_agent_id,
                    provision_mode=activation.provision_mode,
                )
            return PipelineResult.failed(activation.error or "activation_failed")

        if tenant_id is None:
            return PipelineResult()

        from backend.domain.onboarding.orchestrator import get_orchestrator

        orch = get_orchestrator()
        orch_result = await orch.on_intake_submitted(
            tenant_id=str(tenant_id),
            intake_payload=payload,
        )
        return PipelineResult.from_orchestrator(orch_result)
    except Exception as exc:
        logger.warning(
            "onboarding.intake_pipeline_failed tenant_id=%s error=%s",
            tenant_id,
            exc,
        )
        return PipelineResult.failed(str(exc))


def build_intake_response(
    store: IntakeStoreResult,
    pipeline: PipelineResult,
) -> dict[str, Any]:
    """HTTP 200 body when store.stored is True."""
    payload = store.payload
    self_serve = bool(payload.get("self_serve") or payload.get("selfServe"))
    activated = pipeline.activated or (self_serve and pipeline.success)
    response: dict[str, Any] = {
        "ok": True,
        "stored": store.stored,
        "intake_id": store.intake_id,
        "tenant_linked": store.tenant_id is not None or activated,
        "pipeline_advanced": pipeline.success,
        "provision_scheduled": pipeline.provision_scheduled,
        "activated": activated,
        "live_within_minutes": 15 if activated else None,
        "test_call_number": pipeline.test_call_number,
        "inbound_line": pipeline.test_call_number,
        "forward_line": pipeline.forward_number
        or payload.get("forwardNumber")
        or payload.get("forward_number"),
        "retell_agent_id": pipeline.retell_agent_id,
        "provision_mode": pipeline.provision_mode,
    }
    if pipeline.error:
        response["pipeline_error"] = pipeline.error
    return response