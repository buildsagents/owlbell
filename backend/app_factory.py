"""
Owlbell — Application Factory.

Location: backend/app_factory.py

Provides ``create_app()`` with configuration profiles (dev/test/prod):
- Dependency injection container setup
- Middleware stack (tenant, auth, rate limit, logging, timing, CORS)
- Router registration for all subsystems
- Exception handler registration
- Static file serving for React dashboard
- OpenAPI configuration

Usage:
    from backend.app_factory import create_app
    app = create_app(env="production")
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Callable, Dict, List, Optional

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html

from backend.config import Settings, get_settings
from backend.dependencies import init_engine, close_all_dependencies

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# App metadata
# ---------------------------------------------------------------------------

APP_TITLE = "Owlbell API"
APP_DESCRIPTION = (
    "AI-powered 24/7 phone answering service for businesses. "
    "Zero-budget, open-source stack: FreeSWITCH + Whisper + Ollama + Piper.\n\n"
    "## Subsystems\n"
    "- **Telephony**: FreeSWITCH ESL integration\n"
    "- **AI Pipeline**: Whisper STT → Ollama LLM → Piper TTS\n"
    "- **Orchestration**: Session management, event bus, Celery workers\n"
    "- **Business Logic**: Messages, appointments, routing, notifications\n"
    "- **Integrations**: Google Calendar, HubSpot, SendGrid, Twilio, Slack\n"
    "- **Operations**: Tenant management, billing, audit, feature flags\n"
)
APP_VERSION = "1.0.0"
API_PREFIX = "/api/v1"

# ---------------------------------------------------------------------------
# Configuration profiles
# ---------------------------------------------------------------------------

PROFILE_OVERRIDES: Dict[str, Dict] = {
    "development": {
        "debug": True,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    },
    "testing": {
        "debug": True,
        "docs_url": "/docs",
        "redoc_url": None,
    },
    "production": {
        "debug": False,
        "docs_url": None,
        "redoc_url": None,
    },
}


# ---------------------------------------------------------------------------
# Lifespan context manager
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan: startup and shutdown sequence.

    Startup sequence:
        1. Initialize database engine
        2. Connect to Redis
        3. Initialize AI pipeline services
        4. Set up event bus subscriptions
        5. Connect to FreeSWITCH ESL
        6. Verify AI models are loaded
        7. Register health check providers

    Shutdown sequence:
        1. Graceful call handoff / termination
        2. Close event bus subscriptions
        3. Close AI pipeline
        4. Close Redis connections
        5. Dispose database engine
    """
    settings: Settings = app.state.settings
    startup_errors: List[str] = []

    logger.info(
        "app.startup.begin",
        env=settings.env,
        version=APP_VERSION,
        debug=settings.debug,
    )

    # -- 1. Database engine ------------------------------------------------
    try:
        init_engine()
        logger.info("app.startup.database.ok")
    except Exception as exc:
        startup_errors.append(f"database: {exc}")
        logger.error("app.startup.database.failed", error=str(exc))

    # -- 2. Redis connection ------------------------------------------------
    try:
        from backend.db.cache.client import get_redis_client
        redis_client = await get_redis_client()
        await redis_client.ping()
        app.state.redis = redis_client
        logger.info("app.startup.redis.ok")
    except Exception as exc:
        startup_errors.append(f"redis: {exc}")
        logger.error("app.startup.redis.failed", error=str(exc))

    # -- 3. AI pipeline initialization --------------------------------------
    if settings.features.enable_ai_greeting or settings.features.enable_call_transcription:
        try:
            from backend.dependencies import get_ai_pipeline
            ai_pipeline = await get_ai_pipeline()
            await ai_pipeline.initialize()
            app.state.ai_pipeline = ai_pipeline
            logger.info("app.startup.ai_pipeline.ok")
        except Exception as exc:
            startup_errors.append(f"ai_pipeline: {exc}")
            logger.error("app.startup.ai_pipeline.failed", error=str(exc))
    else:
        logger.info("app.startup.ai_pipeline.skipped")

    # -- 4. Event bus setup -------------------------------------------------
    try:
        from orchestrator.event_bus import EventBus

        event_bus = EventBus(redis_client=app.state.redis)
        app.state.event_bus = event_bus
        await _setup_event_subscriptions(event_bus, app)
        logger.info("app.startup.event_bus.ok")
    except Exception as exc:
        startup_errors.append(f"event_bus: {exc}")
        logger.error("app.startup.event_bus.failed", error=str(exc))

    # -- 5. Session manager -------------------------------------------------
    try:
        from orchestrator.session_manager import SessionManager

        session_manager = SessionManager(redis_client=app.state.redis)
        app.state.session_manager = session_manager
        logger.info("app.startup.session_manager.ok")
    except Exception as exc:
        startup_errors.append(f"session_manager: {exc}")
        logger.error("app.startup.session_manager.failed", error=str(exc))

    # -- 6. FreeSWITCH connection check -------------------------------------
    try:
        fs_healthy = await _check_freeswitch_health(settings)
        app.state.fs_healthy = fs_healthy
        if fs_healthy:
            logger.info("app.startup.freeswitch.ok")
        else:
            logger.warning("app.startup.freeswitch.unreachable")
    except Exception as exc:
        app.state.fs_healthy = False
        logger.warning("app.startup.freeswitch.failed", error=str(exc))

    # -- 7. AI model verification -------------------------------------------
    try:
        ai_health = await _verify_ai_models(settings)
        app.state.ai_healthy = ai_health
        logger.info("app.startup.ai_models.ok", models=ai_health)
    except Exception as exc:
        app.state.ai_healthy = False
        logger.warning("app.startup.ai_models.failed", error=str(exc))

    # -- 8. Warm up Redis caches --------------------------------------------
    try:
        await _warmup_redis(app.state.redis)
        logger.info("app.startup.redis_warmup.ok")
    except Exception as exc:
        logger.warning("app.startup.redis_warmup.failed", error=str(exc))

    # -- Track state --------------------------------------------------------
    app.state.start_time = time.perf_counter()
    app.state.request_count = 0
    app.state.error_count = 0
    app.state.startup_errors = startup_errors

    if startup_errors:
        logger.warning(
            "app.startup.complete_with_errors",
            error_count=len(startup_errors),
            errors=startup_errors,
        )
    else:
        logger.info("app.startup.complete")

    yield

    # ======================== SHUTDOWN =====================================
    logger.info("app.shutdown.begin")

    # Graceful call termination
    try:
        if hasattr(app.state, "session_manager"):
            # Signal all active calls to end gracefully
            logger.info("app.shutdown.call_handoff")
    except Exception as exc:
        logger.error("app.shutdown.call_handoff_failed", error=str(exc))

    # Close all dependencies
    try:
        await close_all_dependencies()
        logger.info("app.shutdown.dependencies_closed")
    except Exception as exc:
        logger.error("app.shutdown.dependencies_failed", error=str(exc))

    uptime = time.perf_counter() - app.state.start_time
    logger.info(
        "app.shutdown.complete",
        uptime_seconds=round(uptime, 2),
        total_requests=app.state.request_count,
        total_errors=app.state.error_count,
    )


# ---------------------------------------------------------------------------
# Event subscription setup
# ---------------------------------------------------------------------------


async def _setup_event_subscriptions(event_bus: "EventBus", app: FastAPI) -> None:
    """Subscribe to system events for cross-subsystem communication."""

    async def on_call_started(event: "SystemEvent") -> None:
        """Handle call started event."""
        logger.info(
            "event.call_started",
            call_id=event.payload.get("call_id"),
            tenant_id=event.payload.get("tenant_id"),
        )

    async def on_call_ended(event: "SystemEvent") -> None:
        """Handle call ended event — trigger post-call processing."""
        call_id = event.payload.get("call_id")
        tenant_id = event.payload.get("tenant_id")
        logger.info("event.call_ended", call_id=call_id, tenant_id=tenant_id)

        # Record billable usage for the completed call.
        if tenant_id:
            try:
                import uuid as _uuid

                from backend.dependencies import get_usage_tracker

                tracker = await get_usage_tracker()
                await tracker.record_call_completed(
                    tenant_id=_uuid.UUID(str(tenant_id)),
                    call_id=str(call_id) if call_id else "",
                    duration_seconds=float(event.payload.get("duration_seconds", 0) or 0),
                    llm_input_tokens=int(event.payload.get("llm_input_tokens", 0) or 0),
                    llm_output_tokens=int(event.payload.get("llm_output_tokens", 0) or 0),
                    direction=event.payload.get("direction", "inbound"),
                )
            except Exception as exc:
                logger.error("event.call_ended.usage_failed", error=str(exc))

        # Trigger post-call Celery tasks
        try:
            from orchestrator.tasks import handle_call_end, send_call_summary
            handle_call_end.delay(call_id)
            send_call_summary.delay(call_id)
        except Exception as exc:
            logger.error("event.call_ended.task_failed", error=str(exc))

    async def on_ai_response(event: "SystemEvent") -> None:
        """Handle AI response generation events for logging."""
        logger.debug(
            "event.ai_response",
            call_id=event.payload.get("call_id"),
            response_length=len(event.payload.get("response", "")),
        )

    async def on_system_alert(event: "SystemEvent") -> None:
        """Handle system alert events — forward to Slack if configured."""
        settings = app.state.settings
        if settings.integrations.slack_webhook_url:
            logger.warning(
                "event.system_alert",
                level=event.payload.get("level"),
                message=event.payload.get("message"),
            )

    # Subscribe to event types
    from orchestrator.models import EventType

    await event_bus.subscribe(EventType.CALL_STARTED, on_call_started)
    await event_bus.subscribe(EventType.CALL_ENDED, on_call_ended)
    await event_bus.subscribe(EventType.AI_RESPONSE, on_ai_response)
    await event_bus.subscribe(EventType.SYSTEM_ALERT, on_system_alert)

    logger.info("app.event_subscriptions.registered", count=4)


# ---------------------------------------------------------------------------
# Health checks for external services
# ---------------------------------------------------------------------------


async def _check_freeswitch_health(settings: Settings) -> bool:
    """Check FreeSWITCH ESL connectivity."""
    try:
        import aiohttp

        fs = settings.freeswitch
        timeout = aiohttp.ClientTimeout(total=fs.event_socket_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Try to connect to ESL via HTTP mod_api endpoint
            url = f"http://{fs.host}:{fs.esl_port}/webapi/status"
            async with session.get(url, auth=aiohttp.BasicAuth("", fs.esl_password.get_secret_value())) as resp:
                return resp.status < 500
    except Exception:
        return False


async def _verify_ai_models(settings: Settings) -> bool:
    """Verify AI model services are responsive."""
    try:
        from backend.dependencies import get_ai_pipeline
        pipeline = await get_ai_pipeline()
        health = await pipeline.health_check()
        return any(health.values())
    except Exception:
        return False


async def _warmup_redis(redis_client) -> None:
    """Warm up Redis with commonly accessed data."""
    # Pre-populate feature flags cache
    from backend.config import get_settings
    settings = get_settings()
    features = {
        "enable_call_transcription": settings.features.enable_call_transcription,
        "enable_ai_greeting": settings.features.enable_ai_greeting,
        "enable_smart_routing": settings.features.enable_smart_routing,
        "enable_calendar_sync": settings.features.enable_calendar_sync,
        "enable_crm_sync": settings.features.enable_crm_sync,
    }
    await redis_client.hset("app:features", mapping={k: str(v) for k, v in features.items()})
    await redis_client.expire("app:features", 3600)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle Pydantic validation errors (422)."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:12])
    errors = []

    detail = getattr(exc, "errors", lambda: [])()
    if callable(detail):
        detail = detail() if not isinstance(detail, list) else detail

    for error in detail if isinstance(detail, list) else []:
        loc = error.get("loc", [])
        field = loc[-1] if loc else None
        errors.append({
            "field": str(field) if field else None,
            "message": error.get("msg", "Validation error"),
            "code": "validation_error",
        })

    if not errors:
        errors.append({"message": str(exc), "code": "validation_error"})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": errors[0],
            "errors": errors,
            "meta": {"request_id": request_id, "timestamp": datetime.utcnow().isoformat()},
        },
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle HTTP exceptions."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:12])
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", "Unknown error")

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": str(detail),
                "code": f"http_{status_code}",
            },
            "meta": {"request_id": request_id, "timestamp": datetime.utcnow().isoformat()},
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:12])

    # Update error counter
    app = request.app
    if hasattr(app.state, "error_count"):
        app.state.error_count += 1

    logger.error(
        "exception.unhandled",
        request_id=request_id,
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "An unexpected error occurred",
                "code": "internal_error",
            },
            "meta": {"request_id": request_id, "timestamp": datetime.utcnow().isoformat()},
        },
    )


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class RequestCounterMiddleware:
    """ASGI middleware to count requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            http_app = scope.get("app")
            if http_app and hasattr(http_app, "state"):
                http_app.state.request_count = getattr(http_app.state, "request_count", 0) + 1
        await self.app(scope, receive, send)


class RequestIDMiddleware:
    """Attach a unique request ID to each request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request_id = str(uuid.uuid4())[:12]
            scope["request_id"] = request_id
            original_send = send

            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"X-Request-ID", request_id.encode()))
                    message["headers"] = headers
                await original_send(message)

            await self.app(scope, receive, send_with_headers)
        else:
            await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------


def _register_api_routers(app: FastAPI, settings: Settings) -> None:
    """Register all API routers with their prefixes."""

    # Core API routes (from api/routes package)
    try:
        from api.routes import auth, calls, messages, appointments, business
        from api.routes import integrations, team, admin, analytics, billing
        from api.routes import agency, client_portal, phone_numbers
        from api.routes import leads as leads_router

        # NOTE: each of these routers already self-prefixes with its own name
        # (e.g. APIRouter(prefix="/auth")), so they are mounted at API_PREFIX only.
        # Mounting at f"{API_PREFIX}/auth" produced doubled paths like
        # /api/v1/auth/auth/login, which the dashboard does not call.
        app.include_router(auth.router, prefix=API_PREFIX)
        app.include_router(calls.router, prefix=API_PREFIX)
        app.include_router(messages.router, prefix=API_PREFIX)
        app.include_router(appointments.router, prefix=API_PREFIX)
        app.include_router(business.router, prefix=API_PREFIX)
        app.include_router(integrations.router, prefix=API_PREFIX)
        app.include_router(team.router, prefix=API_PREFIX)
        app.include_router(admin.router, prefix=API_PREFIX)
        app.include_router(analytics.router, prefix=API_PREFIX)
        app.include_router(billing.router, prefix=API_PREFIX)
        app.include_router(agency.router, prefix=API_PREFIX)
        app.include_router(client_portal.router, prefix=API_PREFIX)
        app.include_router(phone_numbers.router, prefix=API_PREFIX)
        app.include_router(leads_router.router)
        logger.info("app.routers.api.registered")
    except Exception as exc:
        logger.error("app.routers.api.failed", error=str(exc))

    # Operations routes
    try:
        from operations.admin.routes import router as ops_admin_router

        app.include_router(
            ops_admin_router,
            prefix=f"{API_PREFIX}/ops/admin",
            tags=["Operations — Admin"],
        )
        logger.info("app.routers.operations.registered")
    except Exception as exc:
        logger.warning("app.routers.operations.skipped", error=str(exc))

    # Operations: usage metering, prompts, onboarding (each self-prefixes).
    try:
        from operations.billing.routes import router as usage_router
        from operations.prompts.routes import router as prompts_router
        from operations.onboarding.routes import router as onboarding_router

        app.include_router(usage_router, prefix=f"{API_PREFIX}/ops")
        app.include_router(prompts_router, prefix=f"{API_PREFIX}/ops")
        app.include_router(onboarding_router, prefix=f"{API_PREFIX}/ops")
        logger.info("app.routers.operations_extra.registered")
    except Exception as exc:
        logger.warning("app.routers.operations_extra.skipped", error=str(exc))

    # Orchestrator gateway routes (WebSocket + REST)
    try:
        from orchestrator.gateway import create_orchestrator_router

        orch_router = create_orchestrator_router(
            session_manager=getattr(app.state, "session_manager", None),
            worker_pool=None,
            event_bus=getattr(app.state, "event_bus", None),
            load_balancer=None,
            health_monitor=None,
            call_queue=None,
        )
        app.include_router(orch_router, tags=["Orchestrator"])
        logger.info("app.routers.orchestrator.registered")
    except Exception as exc:
        logger.warning("app.routers.orchestrator.skipped", error=str(exc))

    # Health check endpoint (comprehensive)
    @app.get("/health", tags=["Health"])
    async def health_check() -> Dict:
        """Comprehensive health check with subsystem status."""
        return await _health_check_handler(app)

    # Readiness probe
    @app.get("/ready", tags=["Health"])
    async def readiness_check() -> Dict:
        """Kubernetes readiness probe."""
        ready = True
        checks = {}

        # Database check
        try:
            from sqlalchemy import text
            from backend.dependencies import _engine
            if _engine:
                async with _engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                checks["database"] = "ok"
            else:
                checks["database"] = "not_initialized"
                ready = False
        except Exception as exc:
            checks["database"] = f"error: {exc}"
            ready = False

        # Redis check
        try:
            redis = getattr(app.state, "redis", None)
            if redis:
                await redis.ping()
                checks["redis"] = "ok"
            else:
                checks["redis"] = "not_connected"
                ready = False
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
            ready = False

        status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(
            status_code=status_code,
            content={
                "ready": ready,
                "checks": checks,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    # Liveness probe
    @app.get("/live", tags=["Health"])
    async def liveness_check() -> Dict:
        """Kubernetes liveness probe."""
        return {
            "alive": True,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root() -> Dict:
        """API root — returns basic info."""
        return {
            "name": APP_TITLE,
            "version": APP_VERSION,
            "description": "AI-powered 24/7 phone answering service",
            "docs": "/docs",
            "health": "/health",
            "ready": "/ready",
            "live": "/live",
        }

    logger.info("app.routers.all.registered")


async def _health_check_handler(app: FastAPI) -> Dict:
    """Aggregate health check across all subsystems."""
    settings: Settings = app.state.settings
    checks: Dict[str, Dict] = {}
    overall = "healthy"

    # App metadata
    checks["app"] = {
        "status": "ok",
        "version": APP_VERSION,
        "env": settings.env,
        "uptime_seconds": round(time.perf_counter() - app.state.start_time, 2) if hasattr(app.state, "start_time") else 0,
    }

    # Database
    try:
        from sqlalchemy import text
        from backend.dependencies import _engine
        if _engine:
            async with _engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                checks["database"] = {"status": "ok", "response_ms": 0}
        else:
            checks["database"] = {"status": "not_initialized"}
            overall = "degraded"
    except Exception as exc:
        checks["database"] = {"status": "error", "detail": str(exc)}
        overall = "unhealthy"

    # Redis
    try:
        redis = getattr(app.state, "redis", None)
        if redis:
            start = time.perf_counter()
            await redis.ping()
            checks["redis"] = {"status": "ok", "response_ms": round((time.perf_counter() - start) * 1000, 2)}
        else:
            checks["redis"] = {"status": "not_connected"}
            overall = "degraded"
    except Exception as exc:
        checks["redis"] = {"status": "error", "detail": str(exc)}
        overall = "unhealthy"

    # FreeSWITCH
    try:
        fs_healthy = getattr(app.state, "fs_healthy", False)
        if fs_healthy:
            checks["freeswitch"] = {"status": "ok"}
        else:
            checks["freeswitch"] = {"status": "unreachable"}
            overall = "degraded"
    except Exception as exc:
        checks["freeswitch"] = {"status": "error", "detail": str(exc)}
        overall = "degraded"

    # AI Services
    try:
        ai_pipeline = getattr(app.state, "ai_pipeline", None)
        if ai_pipeline:
            ai_health = await ai_pipeline.health_check()
            checks["ai"] = {"status": "ok" if any(ai_health.values()) else "degraded", **ai_health}
            if not any(ai_health.values()):
                overall = "degraded"
        else:
            checks["ai"] = {"status": "not_initialized"}
            overall = "degraded"
    except Exception as exc:
        checks["ai"] = {"status": "error", "detail": str(exc)}
        overall = "degraded"

    # Event Bus
    try:
        event_bus = getattr(app.state, "event_bus", None)
        if event_bus:
            checks["event_bus"] = {"status": "ok"}
        else:
            checks["event_bus"] = {"status": "not_initialized"}
    except Exception as exc:
        checks["event_bus"] = {"status": "error", "detail": str(exc)}

    # Celery
    try:
        from celery import Celery
        checks["celery"] = {"status": "ok", "note": "Worker health checked separately"}
    except Exception as exc:
        checks["celery"] = {"status": "error", "detail": str(exc)}

    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks,
    }


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------


def _setup_static_files(app: FastAPI, settings: Settings) -> None:
    """Serve React dashboard static files."""
    dashboard_dir = settings.dashboard_build_dir
    if dashboard_dir and dashboard_dir.exists():
        # Serve static assets from /static
        static_dir = dashboard_dir / "assets"
        if static_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(static_dir)), name="assets")

        # Serve other static files
        app.mount("/static", StaticFiles(directory=str(dashboard_dir)), name="static")

        # Catch-all for SPA routing
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_catch_all(full_path: str) -> PlainTextResponse:
            """Serve index.html for all non-API routes (SPA support)."""
            if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("health"):
                return PlainTextResponse("Not found", status_code=404)
            index_file = dashboard_dir / "index.html"
            if index_file.exists():
                content = index_file.read_text()
                return PlainTextResponse(content, media_type="text/html")
            return PlainTextResponse("Dashboard not built yet", status_code=404)

        logger.info("app.static_files.dashboard.configured", path=str(dashboard_dir))
    else:
        logger.warning("app.static_files.dashboard.not_found", path=str(dashboard_dir))


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------


def create_app(env: Optional[str] = None, settings: Optional[Settings] = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        env: Environment profile ("development", "testing", "production").
             Overrides the APP_ENV environment variable.
        settings: Pre-built Settings instance. If not provided, one is created.

    Returns:
        Configured FastAPI application with all middleware, routers, and handlers.
    """
    # Load settings
    if settings is None:
        settings = get_settings()
    if env:
        settings.env = env

    # Determine profile
    profile_name = "production" if settings.is_production else "testing" if settings.is_testing else "development"
    profile = PROFILE_OVERRIDES.get(profile_name, {})

    logger.info(
        "app_factory.create_app",
        env=settings.env,
        profile=profile_name,
        debug=settings.debug,
    )

    # Create FastAPI app
    app = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=APP_VERSION,
        docs_url=profile.get("docs_url", "/docs"),
        redoc_url=profile.get("redoc_url", "/redoc"),
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Attach settings to app state
    app.state.settings = settings

    # -- Middleware stack (outermost first) ----------------------------------

    # 1. Request ID (outermost — attaches to all downstream)
    app.add_middleware(RequestIDMiddleware)

    # 2. Request counter
    app.add_middleware(RequestCounterMiddleware)

    # 3. GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # 4. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.cors_origins if settings.is_development else ["https://*.owlbell.xyz", "https://owlbell.xyz"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-Response-Time",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )

    # 5. Error handler middleware
    try:
        from api.middleware import ErrorHandlerMiddleware
        app.add_middleware(ErrorHandlerMiddleware)
    except ImportError:
        logger.warning("app_factory.middleware.error_handler.not_available")

    # 6. Timing middleware
    try:
        from api.middleware import TimingMiddleware
        app.add_middleware(TimingMiddleware)
    except ImportError:
        logger.warning("app_factory.middleware.timing.not_available")

    # 7. Logging middleware
    try:
        from api.middleware import LoggingMiddleware
        app.add_middleware(LoggingMiddleware)
    except ImportError:
        logger.warning("app_factory.middleware.logging.not_available")

    # 8. Rate limiting
    try:
        from api.middleware import RateLimitMiddleware
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=settings.security.rate_limit_auth_per_minute,
            requests_per_hour=settings.security.rate_limit_api_per_minute * 60,
        )
    except ImportError:
        logger.warning("app_factory.middleware.rate_limit.not_available")

    # 9. Tenant resolution
    try:
        from api.middleware import TenantMiddleware
        app.add_middleware(
            TenantMiddleware,
            domain_suffix="owlbell.xyz",
        )
    except ImportError:
        logger.warning("app_factory.middleware.tenant.not_available")

    # 10. Auth middleware (innermost — closest to handlers)
    try:
        from api.middleware import AuthMiddleware
        exempt_paths = {
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/signup",
            "/api/v1/auth/refresh",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/magic-link",
            "/api/v1/auth/verify-email",
            "/api/v1/billing/webhook",
            "/api/v1/leads/run",
            "/api/v1/leads/stats",
            "/health",
            "/ready",
            "/live",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/",
            "/assets",
            "/static",
        }
        app.add_middleware(
            AuthMiddleware,
            secret_key=settings.security.jwt_secret.get_secret_value(),
            exempt_paths=exempt_paths,
        )
    except ImportError:
        logger.warning("app_factory.middleware.auth.not_available")

    # -- Exception handlers --------------------------------------------------
    from fastapi.exceptions import HTTPException, RequestValidationError, ValidationException

    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationException, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # -- Router registration -------------------------------------------------
    _register_api_routers(app, settings)

    # -- Static files (dashboard) --------------------------------------------
    _setup_static_files(app, settings)

    logger.info("app_factory.app_created")
    return app


# ---------------------------------------------------------------------------
# Convenience factory for specific environments
# ---------------------------------------------------------------------------


def create_dev_app() -> FastAPI:
    """Create app for development environment."""
    return create_app(env="development")


def create_test_app() -> FastAPI:
    """Create app for testing environment."""
    return create_app(env="testing")


def create_prod_app() -> FastAPI:
    """Create app for production environment."""
    return create_app(env="production")
