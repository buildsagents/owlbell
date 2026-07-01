"""Database readiness for Celery workers and background tasks."""

from __future__ import annotations

import asyncio


def ensure_worker_db() -> None:
    """Initialize (or re-initialize) the async DB engine before task work.

    Celery ``task_prerun`` / ``worker_process_init`` also call this, but task
    bodies and direct test invocations must not rely on those signals alone.

    This helper is synchronous and safe to call from Celery task bodies and
    from code that is already running inside ``run_async``.
    """
    from backend.config import get_settings
    from backend.db import session as db_session
    from backend.db.session import dispose_engine, init_engine

    settings = get_settings()

    if db_session._engine is not None and settings.is_testing:
        expected = settings.database_url
        current = str(db_session._engine.url)
        if current != expected:
            try:
                asyncio.get_running_loop()
                in_async_context = True
            except RuntimeError:
                in_async_context = False

            if in_async_context:
                # Cannot block-dispose while the worker loop is active (testing only).
                db_session._engine = None
                db_session._session_maker = None
            else:
                from workers.async_bridge import run_async

                run_async(dispose_engine())

    init_engine()


__all__ = ["ensure_worker_db"]