"""
Owlbell — Application service dependencies (facade).

Location: backend/dependencies.py

Thin wrappers around the centralized DI container (``backend.di``).
Non-HTTP singletons and service accessors live in ``DependencyContainer``.

FastAPI route DI (auth, tenant, HTTP sessions) lives in ``api.dependencies``.
Database session factory (canonical) lives in ``backend.db.session``.

Usage:
    from backend.di import get_container
    from backend.dependencies import get_ai_pipeline, get_usage_tracker
    from api.dependencies import CurrentUser, get_db_session
    from backend.db.session import open_db_session, require_session_maker
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from backend.di import (
    AIPipelineContext,
    CallManagerContext,
    get_container,
)

logger = logging.getLogger(__name__)

__all__ = [
    "AIPipelineContext",
    "CallManagerContext",
    "close_all_dependencies",
    "get_ai_pipeline",
    "get_call_manager",
    "get_circuit_breaker",
    "get_event_bus",
    "get_prompt_manager",
    "get_redis",
    "get_usage_tracker",
]


async def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client."""
    return await get_container().redis()


async def get_ai_pipeline() -> AIPipelineContext:
    return await get_container().ai_pipeline()


async def get_call_manager() -> CallManagerContext:
    return await get_container().call_manager()


async def get_event_bus() -> "EventBus":
    return await get_container().event_bus()


async def get_circuit_breaker(name: str = "default") -> "CircuitBreaker":
    return await get_container().circuit_breaker(name)


async def get_usage_tracker() -> "UsageTracker":
    return await get_container().usage_tracker()


async def get_prompt_manager() -> "PromptManager":
    return await get_container().prompt_manager()


async def close_all_dependencies() -> None:
    """Close all shared resources (called during shutdown)."""
    await get_container().shutdown()