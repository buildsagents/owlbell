"""Shared embedded Postgres bootstrap for pytest and security_exercise script."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from urllib.parse import urlparse

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_session_loop: asyncio.AbstractEventLoop | None = None


def _ensure_windows_selector_policy() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def get_session_loop() -> asyncio.AbstractEventLoop:
    """Return a persistent session event loop (shared by sync bridge helpers)."""
    global _session_loop
    _ensure_windows_selector_policy()
    if _session_loop is None or _session_loop.is_closed():
        _session_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_session_loop)
    return _session_loop


def asyncio_run(coro):
    """Run a coroutine on the persistent session loop."""
    loop = get_session_loop()
    return loop.run_until_complete(coro)


async def _dispose_engine_async() -> None:
    from backend.db.session import dispose_engine

    await dispose_engine()


def reset_engine() -> None:
    """Dispose the global async engine on the session loop."""
    asyncio_run(_dispose_engine_async())


def close_session_loop() -> None:
    """Tear down the session loop after all async resources are closed."""
    global _session_loop
    if _session_loop is None or _session_loop.is_closed():
        return
    try:
        asyncio_run(_dispose_engine_async())
    finally:
        pending = asyncio.all_tasks(_session_loop)
        for task in pending:
            task.cancel()
        if pending:
            _session_loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        _session_loop.run_until_complete(_session_loop.shutdown_asyncgens())
        _session_loop.close()
        _session_loop = None


def bootstrap_postgres() -> dict:
    """Start pgserver, set env vars, create tables. Idempotent if already bootstrapped."""
    _ensure_windows_selector_policy()

    if os.environ.get("DATABASE_URL") and os.environ.get("APP_ENV") == "testing":
        return {"db_url": os.environ["DATABASE_URL"], "already_running": True}

    import pgserver
    from sqlalchemy.ext.asyncio import create_async_engine

    pgdata = os.environ.get(
        "PYTEST_PGDATA_DIR",
        os.path.join(tempfile.gettempdir(), "owlbell-pytest-pgdata"),
    )
    server = pgserver.get_server(pgdata)
    uri = urlparse(server.get_uri())

    os.environ["APP_ENV"] = "testing"
    os.environ["USE_FAKE_REDIS"] = "1"
    os.environ.setdefault(
        "APP_SECRET_KEY",
        "test-secret-not-for-production-0123456789abcdef0123456789",
    )
    os.environ.setdefault(
        "JWT_SECRET_KEY",
        "test-jwt-not-for-production-0123456789abcdef0123456789",
    )
    os.environ["POSTGRES_HOST"] = uri.hostname or "127.0.0.1"
    os.environ["POSTGRES_PORT"] = str(uri.port or 5432)
    os.environ["POSTGRES_USER"] = uri.username or "postgres"
    os.environ["POSTGRES_PASSWORD"] = uri.password or ""
    os.environ["POSTGRES_DB"] = (uri.path or "/postgres").lstrip("/") or "postgres"

    db_url = (
        f"postgresql+asyncpg://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}"
    )
    os.environ["DATABASE_URL"] = db_url

    from backend.config import get_settings

    get_settings.cache_clear()

    async def _create_tables() -> None:
        from backend.db.models import Base

        engine = create_async_engine(db_url)
        try:
            async with engine.begin() as conn:
                # Fresh schema each session — avoids stale columns from prior model versions
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await engine.dispose()

    asyncio_run(_create_tables())
    return {"server": server, "db_url": db_url, "already_running": False}