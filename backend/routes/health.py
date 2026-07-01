"""Health and readiness endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from backend.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/")
async def root() -> dict:
    return {
        "service": "owlbell-api",
        "status": "ok",
        "docs": None if get_settings().app_env == "production" else "/docs",
    }


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "owlbell-api",
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def ready() -> dict:
    return {"ready": True}


@router.get("/live")
async def live() -> dict:
    return {"alive": True}
