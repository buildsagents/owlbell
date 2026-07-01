"""workers/onboarding_tasks.py - Background Retell provisioning for onboarding.

Dispatches to Celery when ``CELERY_WORKERS_ENABLED=true``; otherwise uses
in-process ``asyncio.create_task``.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import structlog

from workers.async_bridge import run_async

logger = structlog.get_logger(__name__)

_pending: set[str] = set()


def _celery_enabled() -> bool:
    from backend.config import get_settings

    return get_settings().features.enable_celery_workers


def schedule_provision_retell(
    tenant_id: str,
    *,
    intake_payload: Optional[dict[str, Any]] = None,
) -> None:
    """Enqueue Retell provision (Celery worker or in-process asyncio)."""
    if tenant_id in _pending:
        logger.info("onboarding.provision_already_scheduled", tenant_id=tenant_id)
        return
    _pending.add(tenant_id)

    if _celery_enabled():
        try:
            from workers.celery_app import celery_app

            celery_app.send_task(
                "workers.provision_retell",
                kwargs={"tenant_id": tenant_id, "intake_payload": intake_payload},
                queue="onboarding",
            )
            logger.info("onboarding.provision_queued_celery", tenant_id=tenant_id)
            _pending.discard(tenant_id)
            return
        except Exception as exc:
            logger.warning(
                "onboarding.celery_dispatch_failed",
                tenant_id=tenant_id,
                error=str(exc),
            )

    from workers.db import ensure_worker_db

    ensure_worker_db()
    asyncio.create_task(
        _run_provision(tenant_id, intake_payload=intake_payload),
        name=f"provision_retell_{tenant_id}",
    )


async def provision_retell_for_tenant(
    tenant_id: str,
    *,
    intake_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Provision Retell for a tenant and advance the onboarding pipeline."""
    return await _run_provision(tenant_id, intake_payload=intake_payload)


async def _run_provision(
    tenant_id: str,
    *,
    intake_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    from backend.db.session import open_db_session
    from backend.domain.onboarding.orchestrator import get_orchestrator
    from backend.integrations.retell.provision import provision_for_tenant

    try:
        async with open_db_session() as db:
            result = await provision_for_tenant(
                db, tenant_id, intake_payload=intake_payload,
            )
            await db.commit()

        orch = get_orchestrator()
        await orch.on_provision_complete(tenant_id=tenant_id, result=result)
        return result
    except Exception as exc:
        logger.error("onboarding.provision_task_failed", tenant_id=tenant_id, error=str(exc))
        return {"status": "failed", "error": str(exc)}
    finally:
        _pending.discard(tenant_id)


def provision_retell_task(
    tenant_id: str,
    *,
    intake_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Synchronous Celery entrypoint for Retell provisioning."""
    from workers.db import ensure_worker_db

    ensure_worker_db()
    return run_async(
        provision_retell_for_tenant(tenant_id, intake_payload=intake_payload)
    )


def _register_celery_task() -> None:
    from workers.celery_app import celery_app

    celery_app.task(
        name="workers.provision_retell",
        max_retries=2,
        queue="onboarding",
    )(provision_retell_task)


_register_celery_task()