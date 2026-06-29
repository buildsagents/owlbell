"""Pure self-serve sandbox activation pipeline — zero I/O, importable without DB or Retell."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from backend.domain.onboarding.activation_service import provision_sandbox_from_intake
from backend.domain.onboarding.intake_service import (
    IntakeStoreResult,
    PipelineResult,
    build_intake_response,
)


def execute_self_serve_activation(payload: dict[str, Any]) -> dict[str, Any]:
    """Chain provision_sandbox_from_intake → PipelineResult → build_intake_response with no mocks."""
    email = str(payload.get("email") or "")
    business_name = str(
        payload.get("business_name") or payload.get("businessName") or "Business"
    )
    intake_id = str(payload.get("intake_id") or "self-serve")
    tenant_id = payload.get("tenant_id")
    if tenant_id is not None and not isinstance(tenant_id, UUID):
        tenant_id = None

    store = IntakeStoreResult(
        stored=True,
        intake_id=intake_id,
        tenant_id=tenant_id,
        email=email,
        business_name=business_name,
        payload=payload,
    )

    provision = provision_sandbox_from_intake(payload)
    if provision.get("status") != "complete":
        pipeline = PipelineResult.failed(provision.get("error", "provision_failed"))
        return build_intake_response(store, pipeline)

    pipeline = PipelineResult(
        success=True,
        activated=True,
        test_call_number=provision["retell_phone_number"],
        forward_number=provision["forward_number"],
        retell_agent_id=provision["retell_agent_id"],
        provision_mode="sandbox",
    )
    return build_intake_response(store, pipeline)


def pipeline_result_from_response(response: dict[str, Any]) -> PipelineResult:
    """Convert execute_self_serve_activation HTTP body back to PipelineResult."""
    if response.get("pipeline_error"):
        return PipelineResult.failed(str(response["pipeline_error"]))
    if not response.get("activated"):
        return PipelineResult.failed("activation_failed")
    return PipelineResult(
        success=bool(response.get("pipeline_advanced", True)),
        activated=True,
        test_call_number=response.get("inbound_line") or response.get("test_call_number"),
        forward_number=response.get("forward_line"),
        retell_agent_id=response.get("retell_agent_id"),
        provision_mode=response.get("provision_mode", "sandbox"),
    )