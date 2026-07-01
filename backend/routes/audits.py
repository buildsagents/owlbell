"""AI Ops audit endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status

from backend.schemas.audit import AuditRequest, AuditResponse
from backend.services.audit_service import create_audit

router = APIRouter(prefix="/audits", tags=["audits"])


@router.post("", response_model=AuditResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_audit(payload: AuditRequest) -> AuditResponse:
    return create_audit(payload)
