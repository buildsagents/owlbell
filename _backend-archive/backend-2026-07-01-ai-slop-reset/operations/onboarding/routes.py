"""operations/onboarding/routes.py - Agency onboarding pipeline API.

DB-backed onboarding pipeline + email sequence management (agency/admin):
    GET  /onboarding/pipelines                       -> all pipelines
    POST /onboarding/pipelines                       -> create for a tenant
    GET  /onboarding/pipelines/{tenant_id}           -> one pipeline status
    POST /onboarding/pipelines/{tenant_id}/steps/{step_id}/complete
    POST /onboarding/pipelines/{tenant_id}/steps/{step_id}/start
    POST /onboarding/pipelines/{tenant_id}/steps/{step_id}/block
    GET  /onboarding/sequences                        -> all email sequences
    GET  /onboarding/sequences/{tenant_id}           -> one sequence status
    POST /onboarding/sequences/{tenant_id}/send      -> send pending emails

These are agency operations, restricted to admin.
"""

from __future__ import annotations

from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.dependencies import RequireAdmin
from backend.operations.onboarding import automation, email_sequence
from backend.operations.onboarding.email_sequence import EmailStatus, send_email

logger = structlog.get_logger(__name__)
router = APIRouter(
    prefix="/onboarding",
    tags=["Operations — Onboarding"],
    dependencies=[RequireAdmin],
)


def _session_maker():
    """Resolve the global async session maker, or 503 if the DB is down."""
    from backend.db.session import require_session_maker

    try:
        return require_session_maker()
    except RuntimeError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Database not initialized"
        )


class CreatePipelineBody(BaseModel):
    tenant_id: str = Field(..., description="Client tenant UUID")
    tenant_name: str = Field(..., min_length=1, max_length=150)
    tenant_email: str = Field(..., max_length=255)
    contact_name: Optional[str] = None


class StepNotesBody(BaseModel):
    notes: Optional[str] = None
    assignee: Optional[str] = None
    reason: Optional[str] = None


@router.get("/pipelines")
async def list_pipelines() -> dict[str, Any]:
    data = await automation.list_pipelines(_session_maker())
    return {"success": True, "data": data}


@router.post("/pipelines", status_code=status.HTTP_201_CREATED)
async def create_pipeline(body: CreatePipelineBody) -> dict[str, Any]:
    sm = _session_maker()
    pipeline = await automation.create_pipeline(
        sm,
        tenant_id=body.tenant_id,
        tenant_name=body.tenant_name,
        tenant_email=body.tenant_email,
    )
    # Spin up the matching email sequence alongside the pipeline.
    await email_sequence.create_sequence(
        sm,
        tenant_id=body.tenant_id,
        contact_name=body.contact_name or body.tenant_name,
        business_name=body.tenant_name,
        contact_email=body.tenant_email,
        pipeline_id=pipeline.id,
    )
    return {"success": True, "data": pipeline.get_status()}


@router.get("/pipelines/{tenant_id}")
async def get_pipeline(tenant_id: str) -> dict[str, Any]:
    pipeline = await automation.get_pipeline(_session_maker(), tenant_id)
    if pipeline is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pipeline not found")
    return {"success": True, "data": pipeline.get_status()}


@router.post("/pipelines/{tenant_id}/steps/{step_id}/complete")
async def complete_step(
    tenant_id: str, step_id: str, body: StepNotesBody = StepNotesBody()
) -> dict[str, Any]:
    result = await automation.complete_step(
        _session_maker(), tenant_id, step_id, notes=body.notes
    )
    if not result.get("success"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, result.get("error", "Step not found"))
    return {"success": True, "data": result}


@router.post("/pipelines/{tenant_id}/steps/{step_id}/start")
async def start_step(
    tenant_id: str, step_id: str, body: StepNotesBody = StepNotesBody()
) -> dict[str, Any]:
    result = await automation.start_step(
        _session_maker(), tenant_id, step_id, assignee=body.assignee
    )
    if not result.get("success"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, result.get("error", "Step not found"))
    return {"success": True, "data": result}


@router.post("/pipelines/{tenant_id}/steps/{step_id}/block")
async def block_step(
    tenant_id: str, step_id: str, body: StepNotesBody = StepNotesBody()
) -> dict[str, Any]:
    result = await automation.block_step(
        _session_maker(), tenant_id, step_id, reason=body.reason or "blocked"
    )
    if not result.get("success"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, result.get("error", "Step not found"))
    return {"success": True, "data": result}


@router.get("/sequences")
async def list_sequences() -> dict[str, Any]:
    data = await email_sequence.list_sequences(_session_maker())
    return {"success": True, "data": data}


@router.get("/sequences/{tenant_id}")
async def get_sequence(tenant_id: str) -> dict[str, Any]:
    sequence = await email_sequence.get_sequence(_session_maker(), tenant_id)
    if sequence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sequence not found")
    return {"success": True, "data": sequence.get_status()}


@router.post("/sequences/{tenant_id}/send")
async def send_pending(tenant_id: str) -> dict[str, Any]:
    """Send any onboarding emails whose trigger step is complete.

    Pending emails are derived from the pipeline's completed steps; each one is
    rendered, sent (SendGrid → SMTP → log fallback), and its status persisted.
    """
    sm = _session_maker()
    pipeline = await automation.get_pipeline(sm, tenant_id)
    sequence = await email_sequence.get_sequence(sm, tenant_id)
    if pipeline is None or sequence is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pipeline or sequence not found")

    completed = {s.step_id for s in pipeline.steps if s.status.value == "completed"}
    pending = sequence.get_pending_emails(completed)

    sent: list[dict[str, Any]] = []
    for item in pending:
        rendered = sequence.render_email(item["email_id"])
        if rendered is None:
            continue
        result = send_email(
            to=rendered["to"], subject=rendered["subject"], body=rendered["body"]
        )
        new_status = EmailStatus.SENT if result.get("success") else EmailStatus.FAILED
        await email_sequence.mark_email(
            sm, tenant_id, item["email_id"], new_status,
            error=None if result.get("success") else str(result),
        )
        sent.append({"email_id": item["email_id"], "method": result.get("method")})

    return {"success": True, "data": {"sent": sent, "count": len(sent)}}
