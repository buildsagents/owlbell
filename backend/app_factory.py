"""FastAPI application factory for Owlbell.

This is the clean baseline backend after the agency reset. Keep it small:
routes should be explicit, services should do one job, and external
integrations should stay behind adapters.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routes import audits, health, modules, webhooks


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Owlbell API",
        version="0.1.0",
        description="Clean API foundation for the Owlbell AI operations agency.",
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(audits.router, prefix="/api/v1")
    app.include_router(modules.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")

    return app


def create_prod_app() -> FastAPI:
    return create_app()
