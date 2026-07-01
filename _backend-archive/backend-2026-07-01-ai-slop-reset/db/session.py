"""Single source of truth for the async SQLAlchemy engine and session factory.

All process-wide database access goes through this module:

    from backend.db.session import init_engine, require_session_maker, open_db_session

    init_engine()  # optional — lazy-init on first access
    async with open_db_session() as db:
        ...

FastAPI routes should use ``api.dependencies.get_db_session`` (HTTP-aware wrapper).
Workers, domain, integrations, and scripts import from here directly.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> None:
    """Initialize the async SQLAlchemy engine (idempotent; safe to call anytime)."""
    global _engine, _session_maker
    if _engine is not None:
        return

    settings = get_settings()
    db = settings.database
    engine_kwargs: dict = {"echo": settings.is_development}
    if not str(settings.database_url).startswith("sqlite"):
        engine_kwargs.update(
            pool_size=db.effective_pool_size,
            max_overflow=db.effective_max_overflow,
            pool_timeout=db.pool_timeout,
            pool_recycle=db.pool_recycle,
            pool_pre_ping=db.pool_pre_ping,
        )
        if db.is_pooler_url and db.driver == "asyncpg":
            engine_kwargs["connect_args"] = {"statement_cache_size": 0}

    _engine = create_async_engine(settings.database_url, **engine_kwargs)
    if db.is_pooler_url:
        logger.info(
            "db.session.pooler_mode",
            pool_size=db.effective_pool_size,
            max_overflow=db.effective_max_overflow,
        )

    _session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    logger.info("db.session.engine_initialized")


def get_engine() -> AsyncEngine | None:
    """Return the global engine, initializing on first access if needed."""
    if _engine is None:
        init_engine()
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession] | None:
    """Return the global session factory, initializing the engine on first access."""
    if _session_maker is None:
        init_engine()
    return _session_maker


def require_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return the session factory or raise if the engine could not be initialized."""
    maker = get_session_maker()
    if maker is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    return maker


@asynccontextmanager
async def open_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Open a session: commit on success, rollback on error, always close."""
    session = require_session_maker()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async generator for FastAPI ``Depends`` and other DI patterns."""
    async with open_db_session() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose the global engine and clear the session factory."""
    global _engine, _session_maker
    if _engine is None:
        return

    engine = _engine
    _engine = None
    _session_maker = None

    try:
        await engine.dispose()
    except RuntimeError as exc:
        # pytest-asyncio may tear down on a different loop than the one that
        # opened pool connections — fall back to sync pool disposal.
        msg = str(exc).lower()
        if "different loop" in msg or "attached to a different" in msg:
            logger.warning(
                "db.session.engine_dispose_fallback_sync",
                extra={"error": str(exc)},
            )
            try:
                engine.sync_engine.dispose()
            except Exception as sync_exc:
                logger.warning(
                    "db.session.engine_dispose_sync_failed",
                    extra={"error": str(sync_exc)},
                )
        else:
            raise
    logger.info("db.session.engine_disposed")


__all__ = [
    "dispose_engine",
    "get_db_session",
    "get_engine",
    "get_session_maker",
    "init_engine",
    "open_db_session",
    "require_session_maker",
]