"""Repairs verification for test_full_api_walkthrough prefix constants."""

from __future__ import annotations

from tests.e2e import test_full_api_walkthrough as walkthrough


def test_full_api_walkthrough_prefixes_repaired():
    """CALLS_PREFIX and siblings must not be self-referential (prior bug)."""
    assert walkthrough.CALLS_PREFIX == "/api/v1/calls"
    assert walkthrough.MESSAGES_PREFIX == "/api/v1/messages"
    assert walkthrough.APPOINTMENTS_PREFIX == "/api/v1/appointments"
    assert walkthrough.BUSINESS_PREFIX == "/api/v1/business"
    assert walkthrough.INTEGRATIONS_PREFIX == "/api/v1/integrations"
    assert walkthrough.TEAM_PREFIX == "/api/v1/team"
    assert walkthrough.ADMIN_PREFIX == "/api/v1/admin"