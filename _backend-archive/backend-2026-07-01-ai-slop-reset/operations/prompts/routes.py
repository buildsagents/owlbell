"""operations/prompts/routes.py - Prompt management API.

Versioned prompts and A/B testing for the authenticated tenant:
    GET    /prompts/versions                 -> list versions
    POST   /prompts/versions                 -> create a new version (draft)
    GET    /prompts/versions/{id}            -> get one version
    POST   /prompts/versions/{id}/activate   -> activate (archives previous)
    POST   /prompts/versions/{id}/archive    -> archive
    POST   /prompts/defaults                  -> seed default versions
    GET    /prompts/active/{prompt_type}     -> currently active version
    GET    /prompts/performance               -> per-version performance
    GET    /prompts/ab-tests                  -> list A/B tests
    POST   /prompts/ab-tests                  -> start an A/B test
    POST   /prompts/ab-tests/{id}/end        -> end an A/B test

All operations are scoped to the caller's tenant (from the JWT).
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.dependencies import RequireManager
from operations.prompts.manager import PromptType

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/prompts", tags=["Operations — Prompts"])

# Prompt management is a privileged operation (manager+).
_Manager = RequireManager


class CreateVersionBody(BaseModel):
    prompt_type: PromptType
    name: str = Field(..., min_length=1, max_length=150)
    content: str = Field(..., min_length=1)
    variables: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class CreateABTestBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    prompt_type: PromptType
    variant_a_id: uuid.UUID
    variant_b_id: uuid.UUID
    split_percentage: int = Field(50, ge=0, le=100)
    description: Optional[str] = None


@router.get("/versions")
async def list_versions(
    prompt_type: Optional[PromptType] = Query(None),
    include_archived: bool = Query(False),
    user=_Manager,
) -> dict[str, Any]:
    from backend.dependencies import get_prompt_manager

    manager = await get_prompt_manager()
    versions = await manager.list_versions(
        user.tenant_id, prompt_type, include_archived=include_archived
    )
    return {"success": True, "data": [v.to_dict() for v in versions]}


@router.post("/versions", status_code=status.HTTP_201_CREATED)
async def create_version(body: CreateVersionBody, user=_Manager) -> dict[str, Any]:
    from backend.dependencies import get_prompt_manager

    manager = await get_prompt_manager()
    version = await manager.create_version(
        tenant_id=user.tenant_id,
        prompt_type=body.prompt_type,
        name=body.name,
        content=body.content,
        variables=body.variables,
        created_by=user.id,
        notes=body.notes,
    )
    return {"success": True, "data": version.to_dict()}


@router.get("/versions/{version_id}")
async def get_version(version_id: uuid.UUID, user=_Manager) -> dict[str, Any]:
    from backend.dependencies import get_prompt_manager

    manager = await get_prompt_manager()
    version = await manager.get_version(version_id)
    if not version or version.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    return {"success": True, "data": version.to_dict()}


@router.post("/versions/{version_id}/activate")
async def activate_version(version_id: uuid.UUID, user=_Manager) -> dict[str, Any]:
    from backend.dependencies import get_prompt_manager

    manager = await get_prompt_manager()
    existing = await manager.get_version(version_id)
    if not existing or existing.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    version = await manager.activate_version(version_id)
    return {"success": True, "data": version.to_dict()}


@router.post("/versions/{version_id}/archive")
async def archive_version(version_id: uuid.UUID, user=_Manager) -> dict[str, Any]:
    from backend.dependencies import get_prompt_manager

    manager = await get_prompt_manager()
    existing = await manager.get_version(version_id)
    if not existing or existing.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    version = await manager.archive_version(version_id)
    return {"success": True, "data": version.to_dict()}


@router.post("/defaults", status_code=status.HTTP_201_CREATED)
async def create_defaults(user=_Manager) -> dict[str, Any]:
    """Seed the default prompt versions for the tenant (system prompt active)."""
    from backend.dependencies import get_prompt_manager

    manager = await get_prompt_manager()
    versions = await manager.create_default_versions(user.tenant_id, created_by=user.id)
    return {"success": True, "data": [v.to_dict() for v in versions]}


@router.get("/active/{prompt_type}")
async def get_active(prompt_type: PromptType, user=_Manager) -> dict[str, Any]:
    from backend.dependencies import get_prompt_manager

    manager = await get_prompt_manager()
    version = await manager.get_active_version(user.tenant_id, prompt_type)
    return {"success": True, "data": version.to_dict() if version else None}


@router.get("/performance")
async def get_performance(
    prompt_type: Optional[PromptType] = Query(None),
    user=_Manager,
) -> dict[str, Any]:
    from backend.dependencies import get_prompt_manager

    manager = await get_prompt_manager()
    data = await manager.get_prompt_performance(user.tenant_id, prompt_type)
    return {"success": True, "data": data}


@router.get("/ab-tests")
async def list_ab_tests(
    active_only: bool = Query(False),
    user=_Manager,
) -> dict[str, Any]:
    from backend.dependencies import get_prompt_manager

    manager = await get_prompt_manager()
    tests = await manager.list_ab_tests(user.tenant_id, active_only=active_only)
    return {"success": True, "data": [t.to_dict() for t in tests]}


@router.post("/ab-tests", status_code=status.HTTP_201_CREATED)
async def create_ab_test(body: CreateABTestBody, user=_Manager) -> dict[str, Any]:
    from backend.dependencies import get_prompt_manager

    manager = await get_prompt_manager()
    # Ensure both variants belong to the tenant before starting the test.
    for vid in (body.variant_a_id, body.variant_b_id):
        v = await manager.get_version(vid)
        if not v or v.tenant_id != user.tenant_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Version {vid} not found")
    try:
        test = await manager.create_ab_test(
            tenant_id=user.tenant_id,
            name=body.name,
            prompt_type=body.prompt_type,
            variant_a_id=body.variant_a_id,
            variant_b_id=body.variant_b_id,
            split_percentage=body.split_percentage,
            description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return {"success": True, "data": test.to_dict()}


@router.post("/ab-tests/{test_id}/end")
async def end_ab_test(
    test_id: uuid.UUID,
    winning_variant: Optional[str] = Query(None, pattern="^[AB]$"),
    user=_Manager,
) -> dict[str, Any]:
    from backend.dependencies import get_prompt_manager

    manager = await get_prompt_manager()
    existing = await manager.get_ab_test(test_id)
    if not existing or existing.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A/B test not found")
    test = await manager.end_ab_test(test_id, winning_variant=winning_variant)
    return {"success": True, "data": test.to_dict()}
