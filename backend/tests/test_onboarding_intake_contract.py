"""Pytest contract for activation helpers — replaces standalone python -c exercise."""

from __future__ import annotations

import pytest

from backend.domain.onboarding.activation_service import derive_sandbox_inbound_line
from backend.domain.onboarding.self_serve_pipeline import execute_self_serve_activation

pytestmark = pytest.mark.unit


def test_activation_contract_inbound_differs_from_forward():
    email = "gate-test@example.com"
    forward = "(512) 555-0100"
    body = execute_self_serve_activation(
        {"email": email, "businessName": "Gate Co", "selfServe": True, "forwardNumber": forward}
    )
    inbound = body["inbound_line"]
    assert inbound == derive_sandbox_inbound_line(email)
    assert body["forward_line"] == "+15125550100"
    assert body["activated"] is True
    assert inbound != body["forward_line"]