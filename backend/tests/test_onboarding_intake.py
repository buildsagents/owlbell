"""HTTP tests for public onboarding intake endpoint (unit — mocked persistence)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.domain.onboarding.intake_service import (
    IntakeDatabaseError,
    IntakeStoreResult,
    PipelineResult,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_intake_requires_email_and_business_name():
    from api.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post("/api/v1/onboarding/intake", json={"email": "a@b.com"})
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_intake_accepts_camel_case_payload():
    from api.main import app

    store = IntakeStoreResult(
        stored=True,
        intake_id=str(uuid.uuid4()),
        tenant_id=None,
        email="plumber@example.com",
        business_name="Rapid Flow Plumbing",
        payload={"email": "plumber@example.com", "businessName": "Rapid Flow Plumbing"},
    )
    pipeline = PipelineResult(success=True, provision_scheduled=True)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with (
            patch("api.routes.onboarding.persist_intake", new=AsyncMock(return_value=store)),
            patch(
                "api.routes.onboarding.run_pipeline_after_store",
                new=AsyncMock(return_value=pipeline),
            ),
        ):
            res = await client.post(
                "/api/v1/onboarding/intake",
                json={
                    "email": "plumber@example.com",
                    "businessName": "Rapid Flow Plumbing",
                    "sessionId": "cs_test_123",
                    "trade": "Plumbing",
                },
            )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("ok") is True
    assert body.get("stored") is True
    assert "intake_id" in body


@pytest.mark.asyncio
async def test_intake_returns_200_when_pipeline_fails_after_store():
    from api.main import app

    store = IntakeStoreResult(
        stored=True,
        intake_id=str(uuid.uuid4()),
        tenant_id=uuid.uuid4(),
        email="linked@example.com",
        business_name="Linked Plumbing Co",
        payload={},
    )
    pipeline = PipelineResult.failed("[Errno 11004] getaddrinfo failed")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with (
            patch("api.routes.onboarding.persist_intake", new=AsyncMock(return_value=store)),
            patch(
                "api.routes.onboarding.run_pipeline_after_store",
                new=AsyncMock(return_value=pipeline),
            ),
        ):
            res = await client.post(
                "/api/v1/onboarding/intake",
                json={
                    "email": "linked@example.com",
                    "businessName": "Linked Plumbing Co",
                    "sessionId": "cs_pipeline_fail",
                },
            )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("ok") is True
    assert body.get("stored") is True
    assert body.get("pipeline_advanced") is False
    assert "pipeline_error" in body


@pytest.mark.asyncio
async def test_intake_returns_503_when_database_unavailable():
    from api.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch(
            "api.routes.onboarding.persist_intake",
            new=AsyncMock(side_effect=IntakeDatabaseError("Database engine not initialized")),
        ):
            res = await client.post(
                "/api/v1/onboarding/intake",
                json={"email": "x@y.com", "businessName": "Test Co"},
            )

    assert res.status_code == 503, res.text
    assert res.status_code != 405
    assert "Database not initialized" in res.text


@pytest.mark.asyncio
async def test_intake_returns_503_not_500_when_response_builder_fails():
    from api.main import app

    store = IntakeStoreResult(
        stored=True,
        intake_id=str(uuid.uuid4()),
        tenant_id=None,
        email="safe@example.com",
        business_name="Safe Co",
        payload={},
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with (
            patch("api.routes.onboarding.persist_intake", new=AsyncMock(return_value=store)),
            patch(
                "api.routes.onboarding.run_pipeline_after_store",
                new=AsyncMock(return_value=PipelineResult(success=True)),
            ),
            patch(
                "api.routes.onboarding.build_intake_response",
                side_effect=RuntimeError("response builder failed"),
            ),
        ):
            res = await client.post(
                "/api/v1/onboarding/intake",
                json={"email": "safe@example.com", "businessName": "Safe Co"},
            )

    assert res.status_code == 503, res.text
    assert res.status_code != 500
    assert res.status_code != 405
    assert "Database not initialized" not in res.text
    assert "temporarily unavailable" in res.text.lower()


@pytest.mark.asyncio
async def test_intake_route_is_auth_exempt():
    from api.main import app

    store = IntakeStoreResult(
        stored=True,
        intake_id=str(uuid.uuid4()),
        tenant_id=None,
        email="x@y.com",
        business_name="Test Co",
        payload={},
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with (
            patch("api.routes.onboarding.persist_intake", new=AsyncMock(return_value=store)),
            patch(
                "api.routes.onboarding.run_pipeline_after_store",
                new=AsyncMock(return_value=PipelineResult()),
            ),
        ):
            res = await client.post(
                "/api/v1/onboarding/intake",
                json={"email": "x@y.com", "businessName": "Test Co"},
            )
    assert res.status_code != 401