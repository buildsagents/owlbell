"""Security hardening tests — auth middleware, tenant lookup, agent tools."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException, Request

from api.auth_tokens import create_access_token
from api.middleware import TenantMiddleware
from api.routes.agent_tools import _verify_auth
from api.tenant_lookup import lookup_tenant_by_id, tenant_id_from_jwt_header
from backend.db.session import get_session_maker, init_engine
from tests.security_evidence import (
    TenantIsolationFixture,
    assert_analytics_isolation,
    assert_stripe_portal_rejects_cross_tenant_customer,
    seed_isolation_fixture,
    seed_tenant_with_calls,
)


def _make_request(headers: dict | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    return Request(scope)


@pytest_asyncio.fixture
async def client(running_app):
    """HTTP client bound to the session-scoped app lifespan (single event loop)."""
    transport = httpx.ASGITransport(app=running_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


class TestTenantIdFromJwtHeader:
    def test_returns_none_without_bearer(self):
        request = _make_request()
        assert tenant_id_from_jwt_header(request) is None

    def test_returns_tid_from_valid_access_token(self):
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        token = create_access_token(user_id, tenant_id, "admin", "admin@example.com")
        request = _make_request({"Authorization": f"Bearer {token}"})
        assert tenant_id_from_jwt_header(request) == tenant_id

    def test_returns_none_for_invalid_token(self):
        request = _make_request({"Authorization": "Bearer not-a-jwt"})
        assert tenant_id_from_jwt_header(request) is None


class TestVerifyAuthFailClosed:
    def test_rejects_when_secret_not_configured(self):
        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer anything"}
        with patch("api.routes.agent_tools.get_settings") as mock_settings:
            mock_settings.return_value.integrations.retell_agent_tools_secret = None
            with pytest.raises(HTTPException) as exc:
                _verify_auth(request)
        assert exc.value.status_code == 503

    def test_rejects_invalid_bearer_when_secret_configured(self):
        from pydantic import SecretStr

        request = MagicMock(spec=Request)
        request.headers = {"Authorization": "Bearer wrong"}
        with patch("api.routes.agent_tools.get_settings") as mock_settings:
            mock_settings.return_value.integrations.retell_agent_tools_secret = SecretStr("test-secret")
            with pytest.raises(HTTPException) as exc:
                _verify_auth(request)
        assert exc.value.status_code == 401


class TestAnalyticsRequiresAuth:
    @pytest.mark.asyncio
    async def test_metrics_returns_401_without_token(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/analytics/metrics")
        assert resp.status_code == 401


class TestAgencyRequiresSuperAdmin:
    @pytest.mark.asyncio
    async def test_overview_returns_403_for_non_super_admin(self, client: httpx.AsyncClient):
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        token = create_access_token(user_id, tenant_id, "admin", "admin@example.com")
        resp = await client.get(
            "/api/v1/agency/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestTenantHeaderSpoofResistance:
    """End-to-end: mismatched X-Tenant-ID must not bypass JWT tenant or auth."""

    @pytest.mark.asyncio
    async def test_spoofed_header_with_admin_token_still_403_on_agency(self, client: httpx.AsyncClient):
        real_tid = uuid.uuid4()
        spoof_tid = uuid.uuid4()
        token = create_access_token(uuid.uuid4(), real_tid, "admin", "admin@example.com")
        resp = await client.get(
            "/api/v1/agency/overview",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": str(spoof_tid),
            },
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_spoofed_header_does_not_grant_analytics_without_auth(self, client: httpx.AsyncClient):
        spoof_tid = uuid.uuid4()
        resp = await client.get(
            "/api/v1/analytics/metrics",
            headers={"X-Tenant-ID": str(spoof_tid)},
        )
        assert resp.status_code == 401


class TestRetellTestTokenAuth:
    @pytest.mark.asyncio
    async def test_test_token_401_without_bearer(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/webhooks/retell/test-token",
            json={"agent_id": "agent_test"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_test_token_403_for_non_super_admin(self, client: httpx.AsyncClient):
        token = create_access_token(uuid.uuid4(), uuid.uuid4(), "admin", "admin@example.com")
        resp = await client.post(
            "/api/v1/webhooks/retell/test-token",
            json={"agent_id": "agent_test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestPhoneAssignAuth:
    @pytest.mark.asyncio
    async def test_assign_401_without_bearer(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/phone-numbers/assign",
            params={"phone_number": "+15551234567"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_assign_403_for_viewer_role(self, client: httpx.AsyncClient):
        token = create_access_token(uuid.uuid4(), uuid.uuid4(), "viewer", "v@example.com")
        resp = await client.post(
            "/api/v1/phone-numbers/assign",
            params={"phone_number": "+15551234567"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


@pytest_asyncio.fixture
async def analytics_tenant_pair(running_app) -> TenantIsolationFixture:
    """Seed two tenants with calls on the session app loop (no engine reset)."""
    return await seed_isolation_fixture(tenant_a_calls=3, tenant_b_calls=7)


@pytest_asyncio.fixture
async def empty_tenant(running_app) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    await seed_tenant_with_calls(tenant_id, "tenant-empty", "Empty Tenant", call_count=0)
    return tenant_id


class TestBillingPortalCrossTenant:
    @pytest.mark.asyncio
    async def test_portal_rejects_cross_tenant_customer_id(
        self, analytics_tenant_pair: TenantIsolationFixture, client: httpx.AsyncClient
    ):
        status = await assert_stripe_portal_rejects_cross_tenant_customer(
            client, analytics_tenant_pair
        )
        assert status == 403


class TestAnalyticsTenantIsolation:
    """Analytics must return JWT tenant data, ignoring spoofed X-Tenant-ID."""

    @pytest.mark.asyncio
    async def test_metrics_scoped_to_jwt_tenant_not_spoof_header(
        self, analytics_tenant_pair: TenantIsolationFixture, client: httpx.AsyncClient
    ):
        total = await assert_analytics_isolation(client, analytics_tenant_pair)
        assert total == 3
        assert total != analytics_tenant_pair.tenant_b_calls

    @pytest.mark.asyncio
    async def test_metrics_empty_for_tenant_without_calls(
        self, empty_tenant: uuid.UUID, client: httpx.AsyncClient
    ):
        token = create_access_token(uuid.uuid4(), empty_tenant, "admin", "empty@example.com")
        resp = await client.get(
            "/api/v1/analytics/metrics",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["metrics"]["total_calls"] == 0


class TestTenantMiddlewareDbLookup:
    """TenantMiddleware must resolve real tenants from PostgreSQL."""

    @pytest.mark.asyncio
    async def test_lookup_tenant_by_id_from_db(self, running_app):
        tenant_id = uuid.uuid4()
        await seed_tenant_with_calls(tenant_id, "mw-lookup", "Middleware Lookup", call_count=0)

        init_engine()
        session_maker = get_session_maker()
        session = session_maker()
        try:
            data = await lookup_tenant_by_id(session, tenant_id)
        finally:
            await session.close()

        assert data is not None
        assert data["tenant_id"] == tenant_id
        assert data["slug"].startswith("mw-lookup")
        assert data["name"] == "Middleware Lookup"

    @pytest.mark.asyncio
    async def test_middleware_resolves_jwt_tenant_from_db(self, running_app):
        tenant_id = uuid.uuid4()
        await seed_tenant_with_calls(tenant_id, "mw-jwt", "JWT Tenant", call_count=0)

        init_engine()
        middleware = TenantMiddleware(app=MagicMock())
        ctx = await middleware._lookup_tenant(tenant_id)

        assert ctx is not None
        assert ctx.tenant_id == tenant_id
        assert ctx.slug.startswith("mw-jwt")