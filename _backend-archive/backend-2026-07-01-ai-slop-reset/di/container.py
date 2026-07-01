"""Centralized dependency injection container for application services."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import redis.asyncio as aioredis

from backend.di.contexts import AIPipelineContext, CallManagerContext

if TYPE_CHECKING:
    from backend.config import Settings
    from backend.operations.billing.tracker import UsageTracker
    from backend.operations.prompts.manager import PromptManager

logger = logging.getLogger(__name__)

_container: Optional["DependencyContainer"] = None


class DependencyContainer:
    """Single registry for process-wide service singletons.

    HTTP route DI (auth, tenant, per-request DB sessions) stays in
    ``api.dependencies``. Database session factory stays in ``backend.db.session``.
    This container owns long-lived app services only.
    """

    def __init__(self) -> None:
        self._redis: Optional[aioredis.Redis] = None
        self._ai_pipeline: Optional[AIPipelineContext] = None
        self._call_manager: Optional[CallManagerContext] = None
        self._usage_tracker: Optional[UsageTracker] = None
        self._prompt_manager: Optional[PromptManager] = None
        self._started = False

    @property
    def started(self) -> bool:
        return self._started

    async def startup(self, settings: Optional["Settings"] = None) -> None:
        """Warm shared infrastructure (idempotent)."""
        if self._started:
            return

        from backend.db.session import init_engine

        init_engine()

        try:
            from backend.db.cache.client import get_redis_client

            self._redis = await get_redis_client()
            await self._redis.ping()
            logger.info("di.startup.redis_ok")
        except Exception as exc:
            logger.warning("di.startup.redis_failed", extra={"error": str(exc)})

        if settings is not None and not settings.is_testing:
            if settings.features.enable_ai_greeting or settings.features.enable_call_transcription:
                try:
                    await self.ai_pipeline()
                except Exception as exc:
                    logger.warning("di.startup.ai_pipeline_failed", extra={"error": str(exc)})

        self._started = True
        logger.info("di.startup.complete")

    async def shutdown(self) -> None:
        """Release all container-managed resources."""
        from backend.db.session import dispose_engine

        logger.info("di.shutdown.begin")

        self._usage_tracker = None
        self._prompt_manager = None
        self._ai_pipeline = None
        self._call_manager = None
        self._redis = None
        self._started = False

        await dispose_engine()
        logger.info("di.shutdown.complete")

    async def redis(self) -> aioredis.Redis:
        if self._redis is None:
            from backend.db.cache.client import get_redis_client

            self._redis = await get_redis_client()
        return self._redis

    async def ai_pipeline(self) -> AIPipelineContext:
        if self._ai_pipeline is None:
            self._ai_pipeline = AIPipelineContext()
        if not self._ai_pipeline._initialized:
            await self._ai_pipeline.initialize()
        return self._ai_pipeline

    async def call_manager(self) -> CallManagerContext:
        if self._call_manager is None:
            self._call_manager = CallManagerContext()
            await self._call_manager.initialize()
        return self._call_manager

    async def usage_tracker(self) -> "UsageTracker":
        if self._usage_tracker is None:
            from backend.db.session import require_session_maker
            from backend.operations.billing.tracker import UsageTracker

            self._usage_tracker = UsageTracker(session_maker=require_session_maker())
        return self._usage_tracker

    async def prompt_manager(self) -> "PromptManager":
        if self._prompt_manager is None:
            from backend.db.session import require_session_maker
            from backend.operations.prompts.manager import PromptManager

            self._prompt_manager = PromptManager(session_maker=require_session_maker())
        return self._prompt_manager

    async def event_bus(self) -> "EventBus":
        from orchestrator.event_bus import EventBus

        return EventBus(redis_client=await self.redis())

    async def circuit_breaker(self, name: str = "default") -> "CircuitBreaker":
        from orchestrator.circuit_breaker import get_circuit_breaker as _get_cb

        return _get_cb(name, redis_client=await self.redis())


def get_container() -> DependencyContainer:
    """Return the process-wide DI container (created on first access)."""
    global _container
    if _container is None:
        _container = DependencyContainer()
    return _container


def set_container(container: Optional[DependencyContainer]) -> None:
    """Replace the process-wide container (tests and app factory)."""
    global _container
    _container = container


def reset_container() -> None:
    """Clear the process-wide container (tests)."""
    set_container(None)


__all__ = [
    "DependencyContainer",
    "get_container",
    "reset_container",
    "set_container",
]