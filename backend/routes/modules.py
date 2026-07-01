"""Product module endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend.services.module_catalog import list_modules

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get("")
async def modules() -> dict:
    return {"modules": list_modules()}
