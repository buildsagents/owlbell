"""api/main.py - FastAPI application factory for Owlbell.

This module creates and configures the FastAPI application with:
    - Lifespan events (startup/shutdown)
    - CORS middleware
    - Custom exception handlers
    - OpenAPI configuration
    - Router inclusion for all modules
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.middleware import (
    AuthMiddleware,
    ErrorHandlerMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    TenantMiddleware,
    TimingMiddleware,
)
from api.schemas.base import ErrorDetail, ErrorResponse, ResponseMeta

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

APP_TITLE = "Owlbell API"
APP_DESCRIPTION = (
    "AI-powered 24/7 phone answering service. "
    "Zero-budget, open-source stack."
)
APP_VERSION = "1.0.0"
API_PREFIX = "/api/v1"

# CORS origins - configured via env vars in production
DEFAULT_CORS_ORIGINS = [
    "https://owlbell.xyz",
    "https://*.owlbell.xyz",
    "http://localhost:3000",
    "http://localhost:5173",
]

EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/signup",
    "/api/v1/auth/refresh",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/magic-link",
    "/api/v1/auth/verify-email",
    "/api/v1/billing/public-checkout",  # Self-serve checkout from landing page
    "/api/v1/billing/webhook",  # Stripe calls this unauthenticated; verified by signature
    "/api/v1/webhooks/retell",  # Retell calls this unauthenticated; verified by signature
    "/health",
    "/docs",
    "/openapi.json",
}


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info(
        "app.startup",
        version=APP_VERSION,
        api_prefix=API_PREFIX,
    )
    app.state.start_time = time.perf_counter()
    app.state.request_count = 0
    yield
    # Shutdown
    uptime = time.perf_counter() - app.state.start_time
    logger.info(
        "app.shutdown",
        uptime_seconds=round(uptime, 2),
        total_requests=app.state.request_count,
    )


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Pydantic validation errors (422)."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:12])
    errors = []

    # Try to extract validation error details
    detail = getattr(exc, "errors", lambda: [])()
    if callable(detail):
        detail = detail() if not isinstance(detail, list) else detail

    for error in detail if isinstance(detail, list) else []:
        loc = error.get("loc", [])
        field = loc[-1] if loc else None
        errors.append(
            ErrorDetail(
                field=str(field) if field else None,
                message=error.get("msg", "Validation error"),
                code="validation_error",
            )
        )

    if not errors:
        errors.append(
            ErrorDetail(
                message=str(exc), code="validation_error"
            )
        )

    response = ErrorResponse(
        error=errors[0],
        errors=errors,
        meta=ResponseMeta(request_id=request_id),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response.model_dump(),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle HTTP exceptions."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:12])
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", "Unknown error")

    error_detail = ErrorDetail(
        message=str(detail),
        code=f"http_{status_code}",
    )

    response = ErrorResponse(
        error=error_detail,
        meta=ResponseMeta(request_id=request_id),
    )
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:12])

    logger.error(
        "exception.unhandled",
        request_id=request_id,
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
    )

    response = ErrorResponse(
        error=ErrorDetail(
            message="An unexpected error occurred",
            code="internal_error",
        ),
        meta=ResponseMeta(request_id=request_id),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(),
    )


# ---------------------------------------------------------------------------
# Request Counter
# ---------------------------------------------------------------------------


class RequestCounterMiddleware:
    """Simple ASGI middleware to count requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            app = scope.get("app")
            if app and hasattr(app, "state"):
                app.state.request_count = getattr(app.state, "request_count", 0) + 1
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app with all middleware, routes, and handlers.
    """
    app = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Request counter
    app.add_middleware(RequestCounterMiddleware)

    # Error handler middleware (outermost)
    app.add_middleware(ErrorHandlerMiddleware)

    # Timing middleware
    app.add_middleware(TimingMiddleware)

    # Logging middleware
    app.add_middleware(LoggingMiddleware)

    # Rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=100,
        requests_per_hour=5000,
    )

    # Tenant resolution middleware
    app.add_middleware(
        TenantMiddleware,
        domain_suffix="owlbell.xyz",
    )

    # Auth middleware
    app.add_middleware(
        AuthMiddleware,
        secret_key="change-me-in-production",
        exempt_paths=EXEMPT_PATHS,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time", "X-RateLimit-Remaining"],
    )

    # Exception handlers
    from fastapi.exceptions import RequestValidationError, HTTPException

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Include routers
    _include_routers(app)

    # Health check
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """Health check endpoint."""
        uptime = 0.0
        if hasattr(app.state, "start_time"):
            uptime = time.perf_counter() - app.state.start_time
        return {
            "status": "ok",
            "version": APP_VERSION,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": round(uptime, 2),
        }

    @app.get("/", tags=["Root"])
    async def root() -> dict:
        """API root - returns basic info."""
        return {
            "name": APP_TITLE,
            "version": APP_VERSION,
            "docs": "/docs",
            "health": "/health",
        }

    logger.info("app.created", version=APP_VERSION)
    return app


def _include_routers(app: FastAPI) -> None:
    """Register all API routers with their prefixes."""
    from api.routes import auth, calls, messages, appointments, business
    from api.routes import integrations, team, admin, billing
    from api.routes import agency, client_portal, phone_numbers
    from api.routes import retell_webhooks

    app.include_router(auth.router, prefix=f"{API_PREFIX}/auth")
    app.include_router(calls.router, prefix=f"{API_PREFIX}/calls")
    app.include_router(messages.router, prefix=f"{API_PREFIX}/messages")
    app.include_router(appointments.router, prefix=f"{API_PREFIX}/appointments")
    app.include_router(business.router, prefix=f"{API_PREFIX}/business")
    app.include_router(integrations.router, prefix=f"{API_PREFIX}/integrations")
    app.include_router(team.router, prefix=f"{API_PREFIX}/team")
    app.include_router(admin.router, prefix=f"{API_PREFIX}/admin")
    app.include_router(billing.router, prefix=API_PREFIX)  # router self-prefixes with /billing
    app.include_router(agency.router, prefix=API_PREFIX)  # router self-prefixes with /agency
    app.include_router(client_portal.router, prefix=API_PREFIX)  # router self-prefixes with /portal
    app.include_router(phone_numbers.router, prefix=API_PREFIX)  # router self-prefixes with /phone-numbers
    app.include_router(retell_webhooks.router, prefix=API_PREFIX)  # router self-prefixes with /webhooks/retell


# Create the global app instance
app = create_app()
