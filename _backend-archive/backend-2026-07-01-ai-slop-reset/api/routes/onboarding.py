"""api/routes/onboarding.py - Public onboarding intake (post-checkout portal).

Mounted at /api/v1/onboarding by api/main.py and app_factory.py.

    POST /intake  -> persist intake, link tenant, advance pipeline, schedule provision
    GET  /status  -> self-serve onboarding progress by email
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from backend.domain.onboarding.draft_service import (
    load_draft,
    load_draft_by_email,
    save_draft,
)
from backend.domain.onboarding.intake_service import (
    IntakeDatabaseError,
    build_intake_response,
    persist_intake,
    run_pipeline_after_store,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


class IntakeBody(BaseModel):
    """Accepts camelCase from the Next.js onboarding portal."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    email: str
    business_name: str = Field(validation_alias=AliasChoices("business_name", "businessName"))
    session_id: str | None = Field(
        default=None, validation_alias=AliasChoices("session_id", "sessionId")
    )


@router.get("/status")
async def onboarding_status(email: str = Query(..., min_length=3)) -> dict[str, Any]:
    """Self-serve onboarding progress for a customer (no auth)."""
    from backend.domain.onboarding.orchestrator import get_orchestrator

    try:
        orch = get_orchestrator()
    except RuntimeError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database not initialized")

    status_data = await orch.get_status_by_email(email)
    if status_data is None:
        return {"ok": True, "found": False, "pipeline": None}
    return {"ok": True, "found": True, "pipeline": status_data}


@router.post("/intake", status_code=status.HTTP_200_OK)
async def submit_intake(body: IntakeBody) -> dict[str, Any]:
    """Receive post-checkout business intake (no auth — customer not logged in yet)."""
    try:
        return await _submit_intake_body(body)
    except HTTPException:
        raise
    except IntakeDatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not initialized",
        ) from exc
    except Exception as exc:
        logger.warning("onboarding.intake_handler_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Intake temporarily unavailable",
        ) from exc


async def _submit_intake_body(body: IntakeBody) -> dict[str, Any]:
    email = body.email.strip()
    business_name = body.business_name.strip()
    if not email or not business_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="missing_required")

    payload = body.model_dump(mode="json", by_alias=False, exclude_none=True)

    store = await persist_intake(
        email=email,
        business_name=business_name,
        session_id=body.session_id,
        payload=payload,
    )
    pipeline = await run_pipeline_after_store(store.tenant_id, store.payload)

    logger.info(
        "onboarding.intake_received",
        email=email,
        business_name=business_name,
        stored=store.stored,
        tenant_linked=store.tenant_id is not None,
        pipeline_error=pipeline.error,
    )

    return build_intake_response(store, pipeline)


class DraftBody(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    email: str
    step: int = 0
    draft_id: str | None = Field(
        default=None, validation_alias=AliasChoices("draft_id", "draftId")
    )


@router.post("/draft", status_code=status.HTTP_200_OK)
async def upsert_draft(body: DraftBody) -> dict[str, Any]:
    """Save onboarding progress for multi-device resume."""
    try:
        payload = body.model_dump(mode="json", by_alias=False, exclude_none=True)
        email = body.email.strip()
        step = body.step
        draft_id = body.draft_id
        payload.pop("email", None)
        payload.pop("step", None)
        payload.pop("draft_id", None)

        result = await save_draft(
            email=email,
            payload=payload,
            step=step,
            draft_id=draft_id,
        )
        return {
            "ok": True,
            "draft_id": result.draft_id,
            "step": result.step,
            "updated_at": result.updated_at,
        }
    except IntakeDatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not initialized",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/draft")
async def get_draft(
    draft_id: str | None = Query(default=None),
    email: str | None = Query(default=None),
) -> dict[str, Any]:
    """Resume onboarding from another device via draft_id or email."""
    try:
        result = None
        if draft_id:
            result = await load_draft(draft_id=draft_id)
        elif email:
            result = await load_draft_by_email(email)

        if result is None:
            return {"ok": True, "found": False, "draft": None}
        return {
            "ok": True,
            "found": True,
            "draft": {
                "draft_id": result.draft_id,
                "email": result.email,
                "step": result.step,
                "payload": result.payload,
                "updated_at": result.updated_at,
            },
        }
    except IntakeDatabaseError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not initialized",
        ) from exc