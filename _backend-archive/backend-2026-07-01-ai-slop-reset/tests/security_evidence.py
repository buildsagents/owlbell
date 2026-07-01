"""Unified security evidence checks — shared by pytest and scripts/security_exercise.py."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException, Request
from sqlalchemy import select

from api.auth_tokens import create_access_token
from api.middleware import TenantMiddleware
from api.routes.agent_tools import _verify_auth
from api.tenant_lookup import lookup_tenant_by_id
from backend.app_factory import create_app, lifespan
from backend.db.models.call import Call
from backend.db.models.enums import CallDirection, CallStatus, PlanTier, TenantStatus
from backend.db.models.tenant import Tenant
from backend.db.session import get_session_maker, init_engine


@dataclass(frozen=True)
class TenantIsolationFixture:
    tenant_a: uuid.UUID
    tenant_b: uuid.UUID
    user_id: uuid.UUID
    tenant_a_calls: int = 3
    tenant_b_calls: int = 9


async def seed_tenant_with_calls(
    tenant_id: uuid.UUID,
    slug: str,
    name: str,
    call_count: int,
) -> None:
    """Insert tenant + calls using the active engine (no dispose between seeds)."""
    init_engine()
    session_maker = get_session_maker()
    assert session_maker is not None

    unique_slug = f"{slug}-{tenant_id.hex[:8]}"
    now = datetime.utcnow()
    session = session_maker()
    try:
        existing = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        if existing.scalar_one_or_none() is None:
            session.add(
                Tenant(
                    id=tenant_id,
                    slug=unique_slug,
                    name=name,
                    status=TenantStatus.ACTIVE,
                    plan_tier=PlanTier.FREE,
                )
            )
            await session.flush()

        for i in range(call_count):
            session.add(
                Call(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    call_sid=f"CA-{tenant_id.hex[:8]}-{i}",
                    direction=CallDirection.INBOUND,
                    caller_number="+15550001111",
                    destination_number="+15559998888",
                    status=CallStatus.COMPLETED,
                    started_at=now - timedelta(hours=i + 1),
                    duration_seconds=60,
                )
            )
        await session.commit()
    finally:
        await session.close()


async def seed_isolation_fixture(
    tenant_a_calls: int = 3,
    tenant_b_calls: int = 9,
) -> TenantIsolationFixture:
    fixture = TenantIsolationFixture(
        tenant_a=uuid.uuid4(),
        tenant_b=uuid.uuid4(),
        user_id=uuid.uuid4(),
        tenant_a_calls=tenant_a_calls,
        tenant_b_calls=tenant_b_calls,
    )
    await seed_tenant_with_calls(
        fixture.tenant_a, "sec-a", "Tenant A", fixture.tenant_a_calls
    )
    await seed_tenant_with_calls(
        fixture.tenant_b, "sec-b", "Tenant B", fixture.tenant_b_calls
    )
    return fixture


async def assert_stripe_portal_rejects_cross_tenant_customer(
    client: httpx.AsyncClient,
    fixture: TenantIsolationFixture,
) -> int:
    """Portal must reject a Stripe customer_id that belongs to another tenant."""
    own_customer = f"cus_{fixture.tenant_a.hex[:16]}"
    other_customer = f"cus_{fixture.tenant_b.hex[:16]}"

    init_engine()
    session_maker = get_session_maker()
    session = session_maker()
    try:
        result = await session.execute(select(Tenant).where(Tenant.id == fixture.tenant_a))
        tenant = result.scalar_one_or_none()
        assert tenant is not None
        cfg = dict(tenant.config_json or {})
        cfg["stripe_customer_id"] = own_customer
        tenant.config_json = cfg
        await session.commit()
    finally:
        await session.close()

    token = create_access_token(
        fixture.user_id, fixture.tenant_a, "admin", "portal@example.com"
    )
    with patch("api.routes.billing.stripe_service.is_configured", return_value=True):
        resp = await client.post(
            "/api/v1/billing/portal",
            json={"customer_id": other_customer},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    message = body.get("error", {}).get("message", body.get("detail", ""))
    assert "does not belong" in str(message).lower()
    return resp.status_code


async def assert_analytics_isolation(
    client: httpx.AsyncClient,
    fixture: TenantIsolationFixture,
) -> int:
    """Authed analytics with spoofed X-Tenant-ID must return JWT tenant call count."""
    token = create_access_token(
        fixture.user_id, fixture.tenant_a, "admin", "iso@example.com"
    )
    resp = await client.get(
        "/api/v1/analytics/metrics",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": str(fixture.tenant_b),
        },
    )
    assert resp.status_code == 200, resp.text
    total = resp.json()["data"]["metrics"]["total_calls"]
    assert total == fixture.tenant_a_calls, (
        f"expected tenant A count {fixture.tenant_a_calls}, got {total} "
        f"(tenant B has {fixture.tenant_b_calls})"
    )
    assert total != fixture.tenant_b_calls
    return total


async def run_security_checks() -> list[str]:
    """Run all plan step-4 security assertions in one async context."""
    results: list[str] = []
    fixture = await seed_isolation_fixture(tenant_a_calls=3, tenant_b_calls=9)

    app = create_app(env="testing")
    transport = httpx.ASGITransport(app=app)
    async with lifespan(app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            r = await client.get("/api/v1/analytics/metrics")
            results.append(f"analytics_unauth={r.status_code}")
            assert r.status_code == 401, r.text

            tid = uuid.uuid4()
            uid = uuid.uuid4()
            token = create_access_token(uid, tid, "admin", "a@example.com")
            r = await client.get(
                "/api/v1/agency/overview",
                headers={"Authorization": f"Bearer {token}"},
            )
            results.append(f"agency_non_super_admin={r.status_code}")
            assert r.status_code == 403, r.text

            req = MagicMock(spec=Request)
            req.headers = {"Authorization": "Bearer x"}
            with patch("api.routes.agent_tools.get_settings") as ms:
                ms.return_value.integrations.retell_agent_tools_secret = None
                try:
                    _verify_auth(req)
                    results.append("agent_tools_fail_closed=FAIL")
                    raise AssertionError("agent tools should fail closed")
                except HTTPException as exc:
                    results.append(f"agent_tools_fail_closed={exc.status_code}")
                    assert exc.status_code == 503

            spoof_tid = uuid.uuid4()
            r = await client.get(
                "/api/v1/agency/overview",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": str(spoof_tid),
                },
            )
            results.append(f"agency_spoof_header={r.status_code}")
            assert r.status_code == 403

            r = await client.post(
                "/api/v1/webhooks/retell/test-token", json={"agent_id": "x"}
            )
            results.append(f"test_token_unauth={r.status_code}")
            assert r.status_code == 401

            r = await client.post(
                "/api/v1/phone-numbers/assign",
                params={"phone_number": "+15551234567"},
            )
            results.append(f"phone_assign_unauth={r.status_code}")
            assert r.status_code == 401

            r = await client.get("/api/v1/business/profile")
            results.append(f"business_profile_unauth={r.status_code}")
            assert r.status_code == 401, r.text

            total = await assert_analytics_isolation(client, fixture)
            results.append("analytics_authed_spoof_status=200")
            results.append(f"analytics_tenant_a_calls={total}")

            portal_status = await assert_stripe_portal_rejects_cross_tenant_customer(
                client, fixture
            )
            results.append(f"stripe_portal_cross_tenant={portal_status}")

        init_engine()
        sm = get_session_maker()
        session = sm()
        try:
            row = await lookup_tenant_by_id(session, fixture.tenant_a)
        finally:
            await session.close()
        assert row is not None
        results.append(f"tenant_db_lookup_slug={row['slug'][:16]}")
        middleware = TenantMiddleware(app=MagicMock())
        ctx = await middleware._lookup_tenant(fixture.tenant_a)
        assert ctx is not None and ctx.tenant_id == fixture.tenant_a
        results.append("middleware_db_lookup=ok")

    return results


def print_evidence(lines: list[str]) -> None:
    """Emit scratch-dir evidence markers (stdout only, no stderr noise)."""
    print("SECURITY_EXERCISE_OK")
    for line in lines:
        print(line)


def analytics_isolation_via_testclient(client: Any, fixture: TenantIsolationFixture) -> int:
    """Sync TestClient wrapper around the same isolation assertion."""
    token = create_access_token(
        fixture.user_id, fixture.tenant_a, "admin", "iso@example.com"
    )
    resp = client.get(
        "/api/v1/analytics/metrics",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Tenant-ID": str(fixture.tenant_b),
        },
    )
    assert resp.status_code == 200, resp.text
    total = resp.json()["data"]["metrics"]["total_calls"]
    assert total == fixture.tenant_a_calls
    assert total != fixture.tenant_b_calls
    return total