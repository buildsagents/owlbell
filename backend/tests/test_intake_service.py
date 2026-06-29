"""Unit tests for onboarding intake persistence vs pipeline isolation."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from backend.domain.onboarding.intake_service import (
    DatabaseNotReadyError,
    IntakeDatabaseError,
    IntakeStoreResult,
    PipelineResult,
    build_intake_response,
    persist_intake,
    run_pipeline_after_store,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_persist_intake_commits_record(postgres_env):
    tenant_id = uuid.uuid4()
    email = f"svc-{tenant_id.hex[:8]}@example.com"

    from backend.db.models.tenant import Tenant
    from backend.db.session import require_session_maker

    sm = require_session_maker()
    async with sm() as db:
        db.add(
            Tenant(
                id=tenant_id,
                slug=f"svc-{tenant_id.hex[:8]}",
                name="Service Test Co",
                business_email=email,
            )
        )
        await db.commit()

    result = await persist_intake(
        email=email,
        business_name="Service Test Co",
        session_id="cs_unit",
        payload={"email": email, "business_name": "Service Test Co"},
    )

    assert result.stored is True
    assert result.intake_id
    assert result.tenant_id == tenant_id


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_pipeline_after_store_swallows_orchestrator_errors():
    tenant_id = uuid.uuid4()
    failing_orch = AsyncMock()
    failing_orch.on_intake_submitted = AsyncMock(
        side_effect=OSError("[Errno 11004] getaddrinfo failed")
    )

    with patch(
        "backend.domain.onboarding.orchestrator.get_orchestrator",
        return_value=failing_orch,
    ):
        result = await run_pipeline_after_store(
            tenant_id,
            {"email": "x@y.com", "business_name": "Co"},
        )

    assert result.success is False
    assert result.error is not None
    assert "getaddrinfo" in result.error


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_pipeline_after_store_skips_when_no_tenant():
    result = await run_pipeline_after_store(None, {"email": "a@b.com"})
    assert result.success is False
    assert result.error is None


def _mock_session_raising(exc: BaseException):
    mock_sm = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(side_effect=exc)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_sm.return_value = mock_ctx
    return mock_sm


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [
        TypeError("bad type"),
        ValueError("bad value"),
        RuntimeError("runtime"),
        IntegrityError("stmt", {}, Exception("fk")),
        OSError("[Errno 11004] getaddrinfo failed"),
    ],
)
async def test_persist_intake_wraps_all_pre_commit_errors_as_intake_database_error(exc):
    """Every failure inside persist_intake must become IntakeDatabaseError (HTTP 503)."""
    with patch(
        "backend.domain.onboarding.intake_service._require_session_maker",
        return_value=_mock_session_raising(exc),
    ):
        with pytest.raises(IntakeDatabaseError) as raised:
            await persist_intake(
                email="a@b.com",
                business_name="Co",
                session_id=None,
                payload={"email": "a@b.com", "business_name": "Co"},
            )

    assert isinstance(raised.value, IntakeDatabaseError)
    assert type(raised.value) is IntakeDatabaseError


@pytest.mark.unit
@pytest.mark.asyncio
async def test_persist_intake_preserves_database_not_ready_subclass():
    with patch(
        "backend.domain.onboarding.intake_service._require_session_maker",
        side_effect=DatabaseNotReadyError("Database engine not initialized"),
    ):
        with pytest.raises(DatabaseNotReadyError):
            await persist_intake(
                email="a@b.com",
                business_name="Co",
                session_id=None,
                payload={"email": "a@b.com", "business_name": "Co"},
            )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_pipeline_after_store_self_serve_runs_sandbox_activation(monkeypatch):
    """Self-serve sandbox uses pure execute_self_serve_activation — zero mocks."""
    from backend.config import get_settings
    from backend.domain.onboarding.self_serve_pipeline import execute_self_serve_activation

    monkeypatch.setenv("INTEGRATIONS__RETELL_API_KEY", "")
    get_settings.cache_clear()

    email = "pipe@example.com"
    forward = "(512) 555-0100"
    payload = {
        "selfServe": True,
        "email": email,
        "businessName": "Pipe Co",
        "forwardNumber": forward,
    }
    expected = execute_self_serve_activation(payload)

    result = await run_pipeline_after_store(None, payload)

    assert result.success is True
    assert result.activated is True
    assert result.provision_mode == "sandbox"
    assert result.test_call_number == expected["inbound_line"]
    assert result.forward_number == expected["forward_line"]
    assert result.test_call_number != result.forward_number


@pytest.mark.unit
def test_build_intake_response_self_serve_activation_fields():
    from backend.domain.onboarding.activation_service import provision_sandbox_from_intake

    email = "a@b.com"
    forward = "(512) 555-0100"
    sandbox = provision_sandbox_from_intake({"email": email, "forwardNumber": forward})
    store = IntakeStoreResult(
        stored=True,
        intake_id="abc",
        tenant_id=uuid.uuid4(),
        email=email,
        business_name="Co",
        payload={"selfServe": True, "forwardNumber": forward},
    )
    pipeline = PipelineResult(
        success=True,
        activated=True,
        test_call_number=sandbox["retell_phone_number"],
        forward_number=sandbox["forward_number"],
        retell_agent_id=sandbox["retell_agent_id"],
        provision_mode="sandbox",
    )
    body = build_intake_response(store, pipeline)
    assert body["activated"] is True
    assert body["test_call_number"] == sandbox["retell_phone_number"]
    assert body["inbound_line"] == sandbox["retell_phone_number"]
    assert body["forward_line"] == sandbox["forward_number"]
    assert body["test_call_number"] != body["forward_line"]
    assert body["live_within_minutes"] == 15
    assert body["provision_mode"] == "sandbox"


@pytest.mark.unit
def test_build_intake_response_includes_pipeline_error():
    store = IntakeStoreResult(
        stored=True,
        intake_id="abc",
        tenant_id=uuid.uuid4(),
        email="a@b.com",
        business_name="Co",
        payload={},
    )
    pipeline = PipelineResult.failed("boom")

    body = build_intake_response(store, pipeline)

    assert body["ok"] is True
    assert body["stored"] is True
    assert body["pipeline_advanced"] is False
    assert body["pipeline_error"] == "boom"