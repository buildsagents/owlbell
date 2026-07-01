"""Integration tests: Retell + Stripe webhooks write canonical DB rows (Phase 4)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.db.models.call import Call
from backend.db.models.onboarding import OnboardingPipelineRecord
from backend.db.models.tenant import Tenant
from backend.db.models.tenant_integrations import StripeWebhookEvent, TenantIntegrations
from backend.db.models.user import User
from backend.db.session import require_session_maker


@pytest_asyncio.fixture
async def client(running_app):
    transport = httpx.ASGITransport(app=running_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


@pytest.mark.asyncio
async def test_retell_call_started_creates_call_row(client: httpx.AsyncClient):
    """Retell webhook → Call row with retell_call_id and tenant_integrations lookup."""
    sm = require_session_maker()

    tenant_id = uuid.uuid4()
    agent_id = f"agent_{uuid.uuid4().hex[:8]}"
    call_id = f"call_{uuid.uuid4().hex[:12]}"
    phone = "+15551234001"

    async with sm() as db:
        tenant = Tenant(
            id=tenant_id,
            slug=f"wh-integ-{tenant_id.hex[:8]}",
            name="Webhook Test Co",
            business_phone=phone,
            business_email="wh@example.com",
        )
        db.add(tenant)
        db.add(
            TenantIntegrations(
                tenant_id=tenant_id,
                retell_agent_id=agent_id,
                voice_provider="retell",
            )
        )
        await db.commit()

    payload = {
        "event": "call_started",
        "call_id": call_id,
        "phone_number": phone,
        "caller_number": "+15559876543",
        "direction": "inbound",
        "agent_id": agent_id,
        "start_timestamp": 1_700_000_000_000,
    }

    with patch("api.routes.retell_webhooks.verify_webhook", return_value=True):
        res = await client.post(
            "/api/v1/webhooks/retell",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json", "X-Retell-Signature": "test"},
        )

    assert res.status_code == 200

    async with sm() as db:
        row = await db.execute(select(Call).where(Call.retell_call_id == call_id))
        call = row.scalar_one_or_none()
        assert call is not None
        assert call.tenant_id == tenant_id
        assert call.caller_number == "+15559876543"


@pytest.mark.asyncio
async def test_retell_call_started_is_idempotent(client: httpx.AsyncClient):
    sm = require_session_maker()

    tenant_id = uuid.uuid4()
    agent_id = f"agent_{uuid.uuid4().hex[:8]}"
    call_id = f"call_{uuid.uuid4().hex[:12]}"

    async with sm() as db:
        db.add(
            Tenant(
                id=tenant_id,
                slug=f"wh-dup-{tenant_id.hex[:8]}",
                name="Dup Test",
                business_phone="+15551234002",
            )
        )
        db.add(TenantIntegrations(tenant_id=tenant_id, retell_agent_id=agent_id))
        await db.commit()

    payload = {
        "event": "call_started",
        "call_id": call_id,
        "phone_number": "+15551234002",
        "caller_number": "+15551111111",
        "direction": "inbound",
        "agent_id": agent_id,
    }

    with patch("api.routes.retell_webhooks.verify_webhook", return_value=True):
        for _ in range(2):
            res = await client.post(
                "/api/v1/webhooks/retell",
                content=json.dumps(payload),
                headers={"Content-Type": "application/json", "X-Retell-Signature": "x"},
            )
            assert res.status_code == 200

    async with sm() as db:
        rows = await db.execute(select(Call).where(Call.retell_call_id == call_id))
        assert len(rows.scalars().all()) == 1


@pytest.mark.asyncio
async def test_stripe_checkout_creates_tenant_and_pipeline(client: httpx.AsyncClient):
    """Stripe checkout.session.completed → tenant + onboarding pipeline."""
    sm = require_session_maker()

    event_id = f"evt_{uuid.uuid4().hex}"
    email = f"stripe_{uuid.uuid4().hex[:8]}@example.com"
    customer_id = f"cus_{uuid.uuid4().hex[:8]}"
    subscription_id = f"sub_{uuid.uuid4().hex[:8]}"

    fake_event = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": customer_id,
                "subscription": subscription_id,
                "metadata": {"plan": "basic", "tenant_id": ""},
                "customer_details": {"email": email},
                "amount_total": 29700,
                "currency": "usd",
            }
        },
    }

    with patch("api.routes.billing.stripe_service.is_configured", return_value=True):
        with patch("api.routes.billing.stripe_service.construct_event", return_value=fake_event):
            with patch("backend.integrations.stripe.service._send_purchase_alert", return_value=None):
                res = await client.post(
                    "/api/v1/billing/webhook",
                    content=b"{}",
                    headers={"stripe-signature": "sig_test"},
                )

    assert res.status_code == 200
    body = res.json()
    assert body.get("action") == "provisioned"

    async with sm() as db:
        user_row = await db.execute(select(User).where(User.email == email))
        user = user_row.scalar_one_or_none()
        assert user is not None

        integ = await db.execute(
            select(TenantIntegrations).where(TenantIntegrations.stripe_customer_id == customer_id)
        )
        assert integ.scalar_one_or_none() is not None

        pipe = await db.execute(
            select(OnboardingPipelineRecord).where(OnboardingPipelineRecord.tenant_id == user.tenant_id)
        )
        assert pipe.scalar_one_or_none() is not None

        evt = await db.execute(
            select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == event_id)
        )
        assert evt.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_stripe_webhook_duplicate_is_ignored(client: httpx.AsyncClient):
    sm = require_session_maker()

    event_id = f"evt_dup_{uuid.uuid4().hex}"
    fake_event = {
        "id": event_id,
        "type": "invoice.paid",
        "data": {"object": {"customer": "cus_nonexistent"}},
    }

    with patch("api.routes.billing.stripe_service.is_configured", return_value=True):
        with patch("api.routes.billing.stripe_service.construct_event", return_value=fake_event):
            res1 = await client.post("/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "s"})
            res2 = await client.post("/api/v1/billing/webhook", content=b"{}", headers={"stripe-signature": "s"})

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res2.json().get("action") == "duplicate"