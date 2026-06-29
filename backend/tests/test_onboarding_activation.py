"""Unit tests for self-serve activation helpers."""

import pytest

from backend.domain.onboarding.activation_service import (
    derive_sandbox_inbound_line,
    normalize_phone,
    provision_sandbox_from_intake,
)

pytestmark = pytest.mark.unit


def test_normalize_phone_us_10_digit():
    assert normalize_phone("(512) 555-0100") == "+15125550100"


def test_provision_sandbox_requires_forward_number():
    result = provision_sandbox_from_intake({"email": "a@b.co"})
    assert result["status"] == "failed"


def test_provision_sandbox_inbound_differs_from_forward():
    result = provision_sandbox_from_intake(
        {"email": "a@b.co", "forwardNumber": "(512) 555-0199"}
    )
    assert result["status"] == "complete"
    assert result["forward_number"] == "+15125550199"
    assert result["retell_phone_number"] == derive_sandbox_inbound_line("a@b.co")
    assert result["retell_phone_number"] != result["forward_number"]
    assert result["retell_agent_id"].startswith("sandbox_")