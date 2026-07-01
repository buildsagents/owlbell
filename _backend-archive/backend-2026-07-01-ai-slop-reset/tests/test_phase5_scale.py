"""Phase 5 — pooler config, Celery dispatch, analytics rollups."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.config import DatabaseSettings, get_settings
from backend.db.models.call import Call
from backend.db.models.enums import CallDirection, CallStatus
from backend.db.models.tenant import Tenant
from backend.domain.analytics.rollup import fetch_daily_rollups, rollup_tenant_day
from backend.db.session import init_engine
from workers.onboarding_tasks import schedule_provision_retell


def test_pooler_auto_detect_supabase_port():
    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = (
        "postgresql://user:pass@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    )
    try:
        db = DatabaseSettings()
        assert db.is_pooler_url is True
        assert db.effective_pool_size == 5
        assert db.effective_max_overflow == 2
    finally:
        if prev is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prev


def test_pooler_explicit_override():
    db = DatabaseSettings(
        database_url="postgresql://localhost:5432/postgres",
        use_pooler=True,
    )
    assert db.is_pooler_url is True


def test_init_engine_sets_statement_cache_for_pooler():
    import backend.db.session as db_session

    captured: dict = {}

    def _fake_create_engine(url, **kwargs):
        captured.update(kwargs)
        return MagicMock()

    get_settings.cache_clear()
    prev_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "postgresql://u:p@pooler.example.com:6543/db"
    os.environ["DB_USE_POOLER"] = "true"
    get_settings.cache_clear()

    db_session._engine = None
    db_session._session_maker = None
    with patch("backend.db.session.create_async_engine", side_effect=_fake_create_engine):
        init_engine()

    assert captured.get("connect_args") == {"statement_cache_size": 0}
    assert captured.get("pool_size") == 5

    if prev_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = prev_url
    os.environ.pop("DB_USE_POOLER", None)
    get_settings.cache_clear()
    db_session._engine = None
    db_session._session_maker = None


@pytest.mark.asyncio
async def test_rollup_tenant_day_upserts(postgres_env):
    from backend.db.session import get_session_maker

    init_engine()
    sm = get_session_maker()
    tenant_id = uuid4()
    rollup_date = date.today() - timedelta(days=1)
    call_time = datetime.combine(rollup_date, datetime.min.time()) + timedelta(hours=10)

    async with sm() as db:
        db.add(
            Tenant(
                id=tenant_id,
                slug=f"rollup-{tenant_id.hex[:8]}",
                name="Rollup Test",
                business_email=f"rollup-{tenant_id.hex[:8]}@test.com",
            )
        )
        db.add(
            Call(
                tenant_id=tenant_id,
                call_sid=f"sid-{uuid4().hex[:12]}",
                direction=CallDirection.INBOUND,
                caller_number="+15550001111",
                destination_number="+15550002222",
                status=CallStatus.COMPLETED,
                started_at=call_time,
                answered_at=call_time + timedelta(seconds=5),
                duration_seconds=120,
                ai_handled=True,
            )
        )
        await db.commit()

    async with sm() as db:
        result = await rollup_tenant_day(db, tenant_id, rollup_date)
        await db.commit()
        assert result["total_calls"] == 1
        assert result["answered_calls"] == 1

        rollups = await fetch_daily_rollups(db, tenant_id, rollup_date, rollup_date + timedelta(days=1))
        assert rollup_date.isoformat() in rollups
        assert rollups[rollup_date.isoformat()].total_calls == 1


def test_schedule_provision_uses_celery_when_enabled():
    mock_app = MagicMock()
    with patch("workers.onboarding_tasks._celery_enabled", return_value=True):
        with patch("workers.celery_app.celery_app", mock_app):
            schedule_provision_retell(str(uuid4()), intake_payload={"trade": "HVAC"})
    mock_app.send_task.assert_called_once()
    args, kwargs = mock_app.send_task.call_args
    assert args[0] == "workers.provision_retell"
    assert kwargs["queue"] == "onboarding"


def test_celery_app_registers_tasks():
    import workers.analytics_tasks  # noqa: F401 — register beat/onboarding tasks
    import workers.onboarding_tasks  # noqa: F401
    from workers.celery_app import celery_app

    assert "workers.provision_retell" in celery_app.tasks
    assert "workers.rollup_yesterday" in celery_app.tasks
    assert "workers.rollup_day" in celery_app.tasks
    assert "analytics-daily-rollup" in celery_app.conf.beat_schedule


def test_rollup_day_task_runs_without_celery_signals(postgres_env):
    """Direct task invocation must not depend on Celery task_prerun hooks."""
    from backend.db.session import get_session_maker
    from tests.postgres_bootstrap import asyncio_run
    from workers.analytics_tasks import _execute_rollup

    init_engine()
    sm = get_session_maker()
    tenant_id = uuid4()
    rollup_date = date.today() - timedelta(days=1)
    call_time = datetime.combine(rollup_date, datetime.min.time()) + timedelta(hours=12)

    async def _seed():
        async with sm() as db:
            db.add(
                Tenant(
                    id=tenant_id,
                    slug=f"worker-{tenant_id.hex[:8]}",
                    name="Worker Rollup",
                    business_email=f"worker-{tenant_id.hex[:8]}@test.com",
                )
            )
            db.add(
                Call(
                    tenant_id=tenant_id,
                    call_sid=f"sid-{uuid4().hex[:12]}",
                    direction=CallDirection.INBOUND,
                    caller_number="+15550003333",
                    destination_number="+15550004444",
                    status=CallStatus.COMPLETED,
                    started_at=call_time,
                    answered_at=call_time + timedelta(seconds=3),
                    duration_seconds=90,
                    ai_handled=True,
                )
            )
            await db.commit()

    asyncio_run(_seed())

    result = _execute_rollup(rollup_date.isoformat(), tenant_id=str(tenant_id))
    assert result.get("tenants", 0) >= 1


def test_provision_retell_task_runs_without_celery_signals(postgres_env):
    """Direct Celery entrypoint must initialize DB without worker_process_init."""
    from workers.onboarding_tasks import provision_retell_task

    tenant_id = str(uuid4())
    with patch(
        "backend.integrations.retell.provision.provision_for_tenant",
        return_value={"status": "ok", "agent_id": "agent_test"},
    ) as mock_provision:
        with patch(
            "backend.domain.onboarding.orchestrator.OnboardingOrchestrator.on_provision_complete",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = provision_retell_task(tenant_id, intake_payload={"trade": "HVAC"})

    assert result["status"] == "ok"
    mock_provision.assert_called_once()