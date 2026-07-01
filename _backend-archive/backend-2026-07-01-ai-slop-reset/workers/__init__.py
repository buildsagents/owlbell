"""Background workers — Celery tasks for onboarding and analytics."""

from __future__ import annotations

import sys

from backend.import_roots import ensure_import_paths, register_namespace_alias

ensure_import_paths()

__all__ = [
    "celery_app",
    "onboarding_tasks",
    "analytics_tasks",
    "async_bridge",
    "ensure_worker_db",
    "schedule_provision_retell",
    "rollup_yesterday",
]

register_namespace_alias(sys.modules[__name__])


def __getattr__(name: str):
    if name == "celery_app":
        from workers.celery_app import celery_app

        return celery_app
    if name == "onboarding_tasks":
        import workers.onboarding_tasks as onboarding_tasks

        return onboarding_tasks
    if name == "analytics_tasks":
        import workers.analytics_tasks as analytics_tasks

        return analytics_tasks
    if name == "async_bridge":
        import workers.async_bridge as async_bridge

        return async_bridge
    if name == "ensure_worker_db":
        from workers.db import ensure_worker_db

        return ensure_worker_db
    if name == "schedule_provision_retell":
        from workers.onboarding_tasks import schedule_provision_retell

        return schedule_provision_retell
    if name == "rollup_yesterday":
        from workers.analytics_tasks import rollup_yesterday

        return rollup_yesterday
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")