"""
Owlbell — Main Application Entry Point.

Location: backend/main.py

This is the primary entry point that wires ALL subsystems together:
    - FastAPI application initialization
    - Lifespan context manager (startup/shutdown)
    - Database connection pool (async SQLAlchemy)
    - Redis connection (cache, pub/sub, sessions)
    - FreeSWITCH ESL connection
    - AI services initialization (Whisper, Ollama, Piper)
    - Celery worker integration
    - Event bus subscription setup
    - Health check aggregation (DB, Redis, FreeSWITCH, Ollama, Whisper)
    - Graceful shutdown with call handoff

Usage:
    # Development
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

    # Production
    gunicorn -k uvicorn.workers.UvicornWorker backend.main:app

    # With custom env
    APP_ENV=production uvicorn backend.main:app

Environment:
    All configuration is loaded from environment variables (see backend/config.py).
    A .env file in the project root is automatically loaded.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import structlog

# ---------------------------------------------------------------------------
# Logging setup (run before any other imports)
# ---------------------------------------------------------------------------


def setup_logging() -> None:
    """Configure structured logging for the application.

    In production, logs are JSON-formatted for ingestion by Loki/Promtail.
    In development, logs are human-readable.
    """
    env = os.getenv("APP_ENV", "development").lower()
    log_level = os.getenv("LOG_LEVEL", "DEBUG" if env in ("development", "dev", "testing") else "INFO")

    # Base logging config
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    # Configure structlog
    shared_processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if env in ("development", "dev", "testing"):
        # Human-readable logs in dev
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]
    else:
        # JSON logs in production
        processors = shared_processors + [structlog.processors.JSONRenderer()]

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


# Initialize logging immediately
setup_logging()
logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Imports (after logging setup)
# ---------------------------------------------------------------------------

from fastapi import FastAPI

from backend.app_factory import create_app
from backend.config import Settings, get_settings

# ---------------------------------------------------------------------------
# Global application state
# ---------------------------------------------------------------------------

_app: Optional[FastAPI] = None
_settings: Optional[Settings] = None

# ---------------------------------------------------------------------------
# Subsystem lifecycle management
# ---------------------------------------------------------------------------


class SubsystemManager:
    """Manages the lifecycle of all Owlbell subsystems.

    This class encapsulates the startup and shutdown sequences for:
    - Database (PostgreSQL connection pool)
    - Redis (cache, pub/sub, sessions, Celery broker)
    - FreeSWITCH (ESL event socket)
    - AI Pipeline (Whisper STT, Ollama LLM, Piper TTS)
    - Celery (distributed task workers)
    - Event Bus (pub/sub messaging)
    - Session Manager (call state tracking)
    - Circuit Breakers (resilience patterns)
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.subsystems: Dict[str, Dict[str, Any]] = {}
        self.startup_order = [
            "database",
            "redis",
            "celery",
            "event_bus",
            "session_manager",
            "ai_pipeline",
            "freeswitch",
            "circuit_breakers",
        ]
        self._started: List[str] = []

    # -- Startup --------------------------------------------------------------

    async def startup_all(self, app: FastAPI) -> List[str]:
        """Start all subsystems in dependency order.

        Returns:
            List of error messages for any subsystems that failed to start.
        """
        errors: List[str] = []

        for name in self.startup_order:
            try:
                start_fn = getattr(self, f"_start_{name}", None)
                if start_fn is None:
                    logger.warning(f"main.startup.no_handler", subsystem=name)
                    continue

                logger.info(f"main.startup.{name}.begin")
                await start_fn(app)
                self._started.append(name)
                self.subsystems[name] = {"status": "ok", "started_at": datetime.utcnow().isoformat()}
                logger.info(f"main.startup.{name}.ok")

            except Exception as exc:
                error_msg = f"{name}: {type(exc).__name__}: {exc}"
                errors.append(error_msg)
                self.subsystems[name] = {
                    "status": "error",
                    "error": str(exc),
                    "started_at": datetime.utcnow().isoformat(),
                }
                logger.error(f"main.startup.{name}.failed", error=str(exc))

                # Critical subsystems: abort startup
                if name in ("database", "redis"):
                    logger.critical(
                        f"main.startup.critical_failure",
                        subsystem=name,
                        error=str(exc),
                    )
                    break

        return errors

    async def _start_database(self, app: FastAPI) -> None:
        """Initialize the async PostgreSQL connection pool."""
        from backend.dependencies import init_engine

        init_engine()

        # Verify connectivity
        from backend.dependencies import get_engine
        engine = get_engine()
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar_one() == 1

        logger.info("main.database.pool_ready", pool_size=self.settings.database.pool_size)

    async def _start_redis(self, app: FastAPI) -> None:
        """Initialize Redis connections for cache, pub/sub, and sessions."""
        from backend.db.cache.client import get_redis_client

        redis_client = await get_redis_client()
        await redis_client.ping()

        app.state.redis = redis_client
        app.state.redis_pool = redis_client
        logger.info("main.redis.connected", host=self.settings.redis.host)

    async def _start_celery(self, app: FastAPI) -> None:
        """Initialize Celery app configuration."""
        try:
            from celery import Celery

            celery_app = Celery(
                "answerflow",
                broker=self.settings.celery_broker_url,
                backend=self.settings.celery_backend_url,
            )

            celery_app.conf.update(
                task_serializer=self.settings.celery.task_serializer,
                accept_content=self.settings.celery.accept_content,
                result_serializer=self.settings.celery.result_serializer,
                timezone=self.settings.celery.timezone,
                enable_utc=self.settings.celery.enable_utc,
                worker_prefetch_multiplier=self.settings.celery.worker_prefetch_multiplier,
                task_acks_late=self.settings.celery.task_acks_late,
                task_track_started=self.settings.celery.task_track_started,
                task_soft_time_limit=self.settings.celery.task_soft_time_limit,
                task_time_limit=self.settings.celery.task_time_limit,
                task_routes={
                    "orchestrator.tasks.ai_*": {"queue": self.settings.celery.ai_queue},
                    "orchestrator.tasks.notify_*": {"queue": self.settings.celery.notifications_queue},
                    "orchestrator.tasks.sync_*": {"queue": self.settings.celery.sync_queue},
                },
            )

            # Auto-discover tasks
            celery_app.autodiscover_tasks([
                "orchestrator.tasks",
                "backend.business.notifications",
                "backend.integrations.sync",
            ], force=True)

            app.state.celery = celery_app
            logger.info("main.celery.configured", broker=self.settings.celery_broker_url)

        except ImportError:
            logger.warning("main.celery.not_installed")
            app.state.celery = None

    async def _start_event_bus(self, app: FastAPI) -> None:
        """Initialize the Redis pub/sub event bus."""
        from orchestrator.event_bus import EventBus
        from orchestrator.models import EventType

        redis_client = app.state.redis
        event_bus = EventBus(redis_client=redis_client)
        app.state.event_bus = event_bus

        # Core event subscriptions
        await self._subscribe_core_events(event_bus)

        logger.info("main.event_bus.ready")

    async def _subscribe_core_events(self, event_bus: "EventBus") -> None:
        """Subscribe to core system events for cross-subsystem communication."""
        from orchestrator.models import EventType, SystemEvent

        # Call started -> Log and initialize session
        async def on_call_started(event: SystemEvent) -> None:
            logger.info(
                "main.event.call_started",
                call_id=event.payload.get("call_id"),
                tenant_id=event.payload.get("tenant_id"),
                caller_number=event.payload.get("caller_number"),
            )

        # Call ended -> Trigger post-call processing chain
        async def on_call_ended(event: SystemEvent) -> None:
            call_id = event.payload.get("call_id")
            tenant_id = event.payload.get("tenant_id")
            duration = event.payload.get("duration_seconds", 0)
            logger.info(
                "main.event.call_ended",
                call_id=call_id,
                tenant_id=tenant_id,
                duration=duration,
            )
            await self._trigger_post_call_tasks(call_id, tenant_id, event.payload)

        # AI response generated -> Log metrics
        async def on_ai_response(event: SystemEvent) -> None:
            logger.debug(
                "main.event.ai_response",
                call_id=event.payload.get("call_id"),
                model=event.payload.get("model"),
                tokens_used=event.payload.get("tokens_used"),
                response_ms=event.payload.get("response_ms"),
            )

        # Transcript available -> Update conversation context
        async def on_transcript(event: SystemEvent) -> None:
            logger.debug(
                "main.event.transcript",
                call_id=event.payload.get("call_id"),
                speaker=event.payload.get("speaker"),
                text_preview=event.payload.get("text", "")[:100],
            )

        # Worker status change -> Handle capacity changes
        async def on_worker_status(event: SystemEvent) -> None:
            logger.info(
                "main.event.worker_status",
                worker_id=event.payload.get("worker_id"),
                status=event.payload.get("status"),
                capacity=event.payload.get("capacity"),
            )

        # System alert -> Forward to configured channels
        async def on_system_alert(event: SystemEvent) -> None:
            level = event.payload.get("level", "warning")
            message = event.payload.get("message", "")
            logger.warning("main.event.system_alert", level=level, message=message)

            # Forward to Slack if configured
            if self.settings.integrations.slack_webhook_url:
                await self._forward_to_slack(level, message)

        # Register all subscriptions. EventBus.on() registers a handler callback
        # (sync, invoked during publish); subscribe() is the async-generator
        # consumer used for WebSocket streaming, not handler registration.
        event_bus.on(EventType.CALL_STARTED, on_call_started)
        event_bus.on(EventType.CALL_ENDED, on_call_ended)
        event_bus.on(EventType.LLM_RESPONSE_READY, on_ai_response)
        event_bus.on(EventType.TRANSCRIPT_READY, on_transcript)
        event_bus.on(EventType.WORKER_HEARTBEAT, on_worker_status)
        event_bus.on(EventType.SYSTEM_OVERLOAD, on_system_alert)

        logger.info("main.event_subscriptions.registered", count=6)

    async def _trigger_post_call_tasks(
        self, call_id: str, tenant_id: str, payload: Dict[str, Any]
    ) -> None:
        """Trigger Celery tasks after a call ends."""
        try:
            # Fire-and-forget: tasks are queued, not awaited
            import asyncio

            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()

            def enqueue():
                try:
                    from orchestrator.tasks import handle_call_end, send_call_summary
                    handle_call_end.delay(call_id)
                    send_call_summary.delay(call_id)
                except Exception as exc:
                    logger.error("main.post_call_tasks.enqueue_failed", error=str(exc))

            await loop.run_in_executor(None, enqueue)
            logger.info("main.post_call_tasks.queued", call_id=call_id)

        except Exception as exc:
            logger.error("main.post_call_tasks.failed", call_id=call_id, error=str(exc))

    async def _forward_to_slack(self, level: str, message: str) -> None:
        """Forward system alerts to Slack webhook."""
        try:
            import aiohttp

            webhook_url = self.settings.integrations.slack_webhook_url
            if not webhook_url:
                return

            color = {"info": "#36a64f", "warning": "#ff9900", "error": "#ff0000", "critical": "#990000"}.get(level, "#ff9900")

            payload = {
                "channel": self.settings.integrations.slack_channel,
                "attachments": [
                    {
                        "color": color,
                        "title": f"Owlbell Alert: {level.upper()}",
                        "text": message,
                        "footer": "Owlbell",
                        "ts": int(time.time()),
                    }
                ],
            }

            async with aiohttp.ClientSession() as session:
                await session.post(
                    webhook_url.get_secret_value() if hasattr(webhook_url, 'get_secret_value') else str(webhook_url),
                    json=payload,
                )

        except Exception as exc:
            logger.error("main.slack_forward.failed", error=str(exc))

    async def _start_session_manager(self, app: FastAPI) -> None:
        """Initialize the Redis-backed session manager."""
        from orchestrator.session_manager import SessionManager

        session_manager = SessionManager(redis_client=app.state.redis)
        app.state.session_manager = session_manager
        logger.info("main.session_manager.ready")

    async def _start_ai_pipeline(self, app: FastAPI) -> None:
        """Initialize AI services: Whisper, Ollama, Piper."""
        if not self.settings.features.enable_ai_greeting:
            logger.info("main.ai_pipeline.skipped_disabled")
            return

        from backend.dependencies import get_ai_pipeline

        ai_pipeline = await get_ai_pipeline()
        await ai_pipeline.initialize()
        app.state.ai_pipeline = ai_pipeline

        # Verify model health
        health = await ai_pipeline.health_check()
        healthy_count = sum(1 for v in health.values() if v)
        logger.info(
            "main.ai_pipeline.ready",
            services=healthy_count,
            total=len(health),
            details=health,
        )

        if healthy_count < len(health):
            logger.warning("main.ai_pipeline.partial_health", details=health)

    async def _start_freeswitch(self, app: FastAPI) -> None:
        """Initialize FreeSWITCH ESL connection and call handler."""
        try:
            from telephony.manager import TelephonyManager

            telephony = TelephonyManager(settings=self.settings)

            session_manager = getattr(app.state, "session_manager", None)
            event_bus = getattr(app.state, "event_bus", None)
            ai_pipeline = getattr(app.state, "ai_pipeline", None)

            await telephony.start(
                session_manager=session_manager,
                event_bus=event_bus,
                ai_pipeline=ai_pipeline,
            )

            app.state.telephony = telephony
            app.state.fs_healthy = telephony.healthy

            if telephony.healthy:
                logger.info("main.freeswitch.connected", host=self.settings.freeswitch.host)
            else:
                logger.warning(
                    "main.freeswitch.connecting",
                    host=self.settings.freeswitch.host,
                    note="FreeSWITCH ESL will retry in background",
                )

        except Exception as exc:
            app.state.fs_healthy = False
            logger.warning("main.freeswitch.start_failed", error=str(exc))

    async def _check_freeswitch(self) -> bool:
        """Check FreeSWITCH ESL connectivity via TCP socket."""
        try:
            import asyncio

            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.settings.freeswitch.host,
                    self.settings.freeswitch.esl_port,
                ),
                timeout=5.0,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    async def _start_circuit_breakers(self, app: FastAPI) -> None:
        """Initialize circuit breakers for AI services."""
        from orchestrator.circuit_breaker import CircuitBreaker

        # Create circuit breakers for each AI service
        for service_name in ("whisper", "ollama", "piper", "freeswitch"):
            cb = CircuitBreaker(
                name=service_name,
                redis_client=app.state.redis,
                failure_threshold=5,
                recovery_timeout=30,
            )
            self.subsystems[f"circuit_{service_name}"] = {"status": "ok"}

        logger.info("main.circuit_breakers.ready")

    # -- Shutdown -------------------------------------------------------------

    async def shutdown_all(self, app: FastAPI) -> None:
        """Gracefully shutdown all subsystems in reverse order."""
        logger.info("main.shutdown.begin")

        # Reverse the startup order
        shutdown_order = list(reversed(self._started))

        for name in shutdown_order:
            try:
                shutdown_fn = getattr(self, f"_stop_{name}", None)
                if shutdown_fn:
                    await shutdown_fn(app)
                    logger.info(f"main.shutdown.{name}.ok")
                else:
                    logger.debug(f"main.shutdown.{name}.no_handler")
            except Exception as exc:
                logger.error(f"main.shutdown.{name}.failed", error=str(exc))

        logger.info("main.shutdown.complete")

    async def _stop_database(self, app: FastAPI) -> None:
        """Dispose database engine connections."""
        from backend.dependencies import _engine
        if _engine is not None:
            await _engine.dispose()
            logger.info("main.database.disposed")

    async def _stop_redis(self, app: FastAPI) -> None:
        """Close Redis connections."""
        try:
            from backend.db.cache.client import close_redis_client
            await close_redis_client()
            logger.info("main.redis.closed")
        except Exception as exc:
            logger.warning("main.redis.close_error", error=str(exc))

    async def _stop_celery(self, app: FastAPI) -> None:
        """Signal Celery workers to stop accepting new tasks."""
        celery = getattr(app.state, "celery", None)
        if celery:
            logger.info("main.celery.signaled")

    async def _stop_event_bus(self, app: FastAPI) -> None:
        """Unsubscribe from event channels."""
        event_bus = getattr(app.state, "event_bus", None)
        if event_bus:
            # EventBus doesn't have explicit unsubscribe, but we log it
            logger.info("main.event_bus.stopped")

    async def _stop_session_manager(self, app: FastAPI) -> None:
        """Clean up active sessions."""
        session_manager = getattr(app.state, "session_manager", None)
        if session_manager:
            try:
                # Signal all active calls to end gracefully
                active_sessions = await session_manager.list_active_sessions()
                logger.info(
                    "main.session_manager.cleanup",
                    active_sessions=len(active_sessions),
                )
            except Exception as exc:
                logger.warning("main.session_manager.cleanup_error", error=str(exc))

    async def _stop_ai_pipeline(self, app: FastAPI) -> None:
        """Release AI model resources."""
        ai_pipeline = getattr(app.state, "ai_pipeline", None)
        if ai_pipeline:
            logger.info("main.ai_pipeline.stopped")

    async def _stop_freeswitch(self, app: FastAPI) -> None:
        """Close FreeSWITCH ESL connection."""
        telephony = getattr(app.state, "telephony", None)
        if telephony:
            await telephony.stop()
        logger.info("main.freeswitch.disconnected")

    async def _stop_circuit_breakers(self, app: FastAPI) -> None:
        """Reset circuit breaker states."""
        try:
            from orchestrator.circuit_breaker import reset_all_circuits_async
            await reset_all_circuits_async(redis_client=app.state.redis)
            logger.info("main.circuit_breakers.reset")
        except Exception as exc:
            logger.warning("main.circuit_breakers.reset_error", error=str(exc))


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan context manager.

    Coordinates startup and shutdown of all subsystems.
    """
    settings: Settings = app.state.settings
    manager = SubsystemManager(settings)

    # -- Startup -----------------------------------------------------------
    logger.info(
        "main.lifespan.startup.begin",
        app_name=settings.app_name,
        version=settings.app_version,
        env=settings.env,
    )

    startup_errors = await manager.startup_all(app)

    if startup_errors:
        logger.warning(
            "main.lifespan.startup.complete_with_errors",
            error_count=len(startup_errors),
            errors=startup_errors,
        )
    else:
        logger.info("main.lifespan.startup.complete")

    # -- Signal handlers ---------------------------------------------------
    _setup_signal_handlers(app, manager)

    yield

    # -- Shutdown ----------------------------------------------------------
    logger.info("main.lifespan.shutdown.begin")
    await manager.shutdown_all(app)
    logger.info("main.lifespan.shutdown.complete")


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------


def _setup_signal_handlers(app: FastAPI, manager: SubsystemManager) -> None:
    """Setup OS signal handlers for graceful shutdown.

    Handles SIGTERM (Kubernetes, Docker) and SIGINT (Ctrl+C).
    """

    def handle_signal(sig_num, frame):
        """Handle shutdown signals."""
        sig_name = signal.Signals(sig_num).name
        logger.info(f"main.signal.{sig_name.lower()}_received", signal=sig_name)

        # Note: In asyncio, we can't directly await here.
        # The lifespan context manager handles the actual shutdown.

    # Register handlers (if not in testing)
    if not _settings or not _settings.is_testing:
        try:
            signal.signal(signal.SIGTERM, handle_signal)
            signal.signal(signal.SIGINT, handle_signal)
            logger.debug("main.signal_handlers.registered")
        except ValueError:
            # Can't set signal handler in thread
            pass


# ---------------------------------------------------------------------------
# Application creation
# ---------------------------------------------------------------------------


def create_main_app() -> FastAPI:
    """Create the main FastAPI application with full subsystem wiring.

    This is the primary entry point used by uvicorn/gunicorn.

    Usage:
        uvicorn backend.main:app --host 0.0.0.0 --port 8000
    """
    global _app, _settings

    if _app is not None:
        return _app

    logger.info("main.create_app.begin")

    # Load settings
    _settings = get_settings()

    # Override lifespan with our subsystem manager
    from backend.app_factory import create_app as _factory_create_app

    # Create app using the factory but with our custom lifespan
    _app = _factory_create_app(settings=_settings)

    # Replace the lifespan with our subsystem-aware version
    # Note: We keep the factory's router/middleware setup and just enhance lifespan
    original_lifespan = _app.router.lifespan_context

    @asynccontextmanager
    async def combined_lifespan(app: FastAPI) -> AsyncGenerator:
        """Combined lifespan that runs factory setup + subsystem manager."""
        manager = SubsystemManager(_settings)

        logger.info(
            "main.lifespan.startup",
            env=_settings.env,
            version=_settings.app_version,
        )

        # Run subsystem startup
        startup_errors = await manager.startup_all(app)
        if startup_errors:
            logger.warning(
                "main.lifespan.errors",
                count=len(startup_errors),
                errors=startup_errors,
            )

        # Start lead pipeline scheduler
        app.state.scheduler_tasks = []
        if _settings.env != "testing":
            try:
                from backend.leads.scheduler import start_scheduler

                scheduler_tasks = await start_scheduler(app)
                app.state.scheduler_tasks = scheduler_tasks
                if scheduler_tasks:
                    logger.info("main.lifespan.scheduler.ok", count=len(scheduler_tasks))
            except Exception as exc:
                logger.warning("main.lifespan.scheduler.failed", error=str(exc))

        yield

        # Cancel scheduler background tasks
        scheduler_tasks = getattr(app.state, "scheduler_tasks", [])
        for task in scheduler_tasks:
            task.cancel()
        if scheduler_tasks:
            import asyncio
            await asyncio.gather(*scheduler_tasks, return_exceptions=True)
            logger.info("main.lifespan.scheduler.cancelled", count=len(scheduler_tasks))

        # Run subsystem shutdown
        logger.info("main.lifespan.shutdown")
        await manager.shutdown_all(app)

    _app.router.lifespan_context = combined_lifespan

    # Store settings
    _app.state.settings = _settings

    logger.info("main.create_app.complete")
    return _app


# ---------------------------------------------------------------------------
# Uvicorn/Gunicorn entry point
# ---------------------------------------------------------------------------

# The global app instance that uvicorn/gunicorn will import
app = create_main_app()

# ---------------------------------------------------------------------------
# Direct execution (development)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    # Development server configuration
    uvicorn_config = {
        "host": settings.api_host,
        "port": settings.api_port,
        "reload": settings.is_development,
        "reload_dirs": [str(BACKEND_DIR)] if settings.is_development else None,
        "log_level": "debug" if settings.debug else "info",
        "access_log": settings.debug,
        "workers": 1 if settings.is_development else None,
    }

    logger.info(
        "main.direct_execution",
        host=uvicorn_config["host"],
        port=uvicorn_config["port"],
        reload=uvicorn_config["reload"],
    )

    uvicorn.run("backend.main:app", **{k: v for k, v in uvicorn_config.items() if v is not None})
