"""Self-serve pipeline — one zero-mock test + one handler test (persist_intake only)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import httpx
import pytest

from backend.domain.onboarding.activation_service import provision_sandbox_from_intake
from backend.domain.onboarding.intake_service import IntakeStoreResult
from backend.domain.onboarding.self_serve_pipeline import execute_self_serve_activation

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def sandbox_env_without_retell(monkeypatch):
    """Ensure pure sandbox pipeline runs without Retell credentials in dev .env."""
    monkeypatch.setenv("INTEGRATIONS__RETELL_API_KEY", "")
    from backend.config import get_settings

    get_settings.cache_clear()


REPRESENTATIVE_PAYLOAD = {
    "email": "pipeline@example.com",
    "businessName": "Pipeline Plumbing Co",
    "selfServe": True,
    "forwardNumber": "(512) 555-0100",
    "trade": "Plumbing",
    "voiceId": "warm_professional",
    "pricingTier": "growth",
}

# Mirrors onboarding/page.tsx submit payload (expanded wizard fields).
EXPANDED_WIZARD_PAYLOAD = {
    **REPRESENTATIVE_PAYLOAD,
    "serviceArea": "Austin, TX",
    "website": "https://pipeline.example.com",
    "numberChoice": "forward",
    "hours": "Mon-Fri 8am-6pm",
    "emergency": "book_next",
    "emergencyRouting": "book_next_slot",
    "billingCycle": "annual",
    "addOns": ["extra_number", "custom_voice"],
    "greeting": "Thanks for calling Pipeline Plumbing",
    "tone": "warm",
    "topServices": "Drain cleaning, water heaters",
    "faq": "We offer 24/7 emergency service",
    "calendar": "google",
    "crmProvider": "jobber",
    "smsNumber": "pipeline@example.com",
    "kbFileNames": ["price-sheet.pdf"],
}


def test_execute_self_serve_activation_zero_mocks():
    """Imports only self_serve_pipeline — no DB, Retell, or HTTP mocks."""
    body = execute_self_serve_activation(REPRESENTATIVE_PAYLOAD)
    expected = provision_sandbox_from_intake(REPRESENTATIVE_PAYLOAD)

    assert body["ok"] is True
    assert body["activated"] is True
    assert body["provision_mode"] == "sandbox"
    assert body["inbound_line"] == expected["retell_phone_number"]
    assert body["forward_line"] == expected["forward_number"]
    assert body["inbound_line"] != body["forward_line"]
    assert body["retell_agent_id"] == expected["retell_agent_id"]


def test_execute_self_serve_activation_accepts_expanded_wizard_fields():
    """Expanded onboarding config fields pass through without mocks."""
    body = execute_self_serve_activation(EXPANDED_WIZARD_PAYLOAD)
    assert body["ok"] is True
    assert body["activated"] is True
    assert body["provision_mode"] == "sandbox"
    assert body["inbound_line"] != body["forward_line"]


@pytest.mark.asyncio
async def test_intake_handler_patches_only_persist_intake():
    """POST /onboarding/intake — only DB persist stubbed; pipeline is pure sandbox."""
    from api.main import app

    async def stub_persist_intake(**kwargs):
        return IntakeStoreResult(
            stored=True,
            intake_id=str(uuid.uuid4()),
            tenant_id=None,
            email=kwargs["email"],
            business_name=kwargs["business_name"],
            payload=kwargs["payload"],
        )

    expected = execute_self_serve_activation(REPRESENTATIVE_PAYLOAD)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch("api.routes.onboarding.persist_intake", new=stub_persist_intake):
            res = await client.post("/api/v1/onboarding/intake", json=REPRESENTATIVE_PAYLOAD)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["activated"] is True
    assert body["inbound_line"] == expected["inbound_line"]
    assert body["forward_line"] == expected["forward_line"]


@pytest.mark.asyncio
async def test_intake_handler_persists_expanded_wizard_payload():
    """Handler stores full wizard payload from onboarding portal — persist_intake stub only."""
    from api.main import app

    captured: dict = {}

    async def stub_persist_intake(**kwargs):
        captured.update(kwargs)
        return IntakeStoreResult(
            stored=True,
            intake_id=str(uuid.uuid4()),
            tenant_id=None,
            email=kwargs["email"],
            business_name=kwargs["business_name"],
            payload=kwargs["payload"],
        )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch("api.routes.onboarding.persist_intake", new=stub_persist_intake):
            res = await client.post("/api/v1/onboarding/intake", json=EXPANDED_WIZARD_PAYLOAD)

    assert res.status_code == 200, res.text
    assert captured["payload"]["crmProvider"] == "jobber"
    assert captured["payload"]["calendar"] == "google"
    assert captured["payload"]["pricingTier"] == "growth"
    assert captured["payload"]["voiceId"] == "warm_professional"
    assert captured["payload"]["emergencyRouting"] == "book_next_slot"
    assert captured["payload"]["emergency"] == "book_next"
    assert captured["payload"]["addOns"] == ["extra_number", "custom_voice"]
    assert captured["payload"]["billingCycle"] == "annual"
    assert "forwardNumber" in captured["payload"]
    assert "inbound_line" not in captured["payload"]