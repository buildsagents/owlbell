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