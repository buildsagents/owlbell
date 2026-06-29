"""Unit tests for server-side script version history.

DB persistence and RAG re-index are exercised in business.py routes against TenantConfig;
this module tests the pure merge logic (same as append_script_version in the route handler).
Full Postgres roundtrip requires pgserver (skipped on Windows gates — plan non-goal).
"""

import pytest

from backend.domain.scripts.version_service import append_script_version, list_script_versions

pytestmark = pytest.mark.unit


def test_append_and_list_script_versions():
    cfg, v1 = append_script_version({}, script_key="greeting", content="Hello there")
    assert v1["content"] == "Hello there"
    rows = list_script_versions(cfg, "greeting")
    assert len(rows) == 1
    cfg, v2 = append_script_version(cfg, script_key="greeting", content="Hi caller")
    rows = list_script_versions(cfg, "greeting")
    assert len(rows) == 2
    assert rows[0]["content"] == "Hi caller"


def test_tenant_config_roundtrip_like_business_route():
    """Simulates TenantConfig.ai_settings load → append → flush pattern from business.py."""
    tenant_config = {"ai_settings": {"voice_id": "warm_professional"}}
    ai = dict(tenant_config["ai_settings"])

    ai, v1 = append_script_version(ai, script_key="greeting", content="Thanks for calling")
    tenant_config["ai_settings"] = ai

    ai2 = dict(tenant_config["ai_settings"])
    ai2, v2 = append_script_version(ai2, script_key="greeting", content="Thank you for calling")
    tenant_config["ai_settings"] = ai2

    rows = list_script_versions(tenant_config["ai_settings"], "greeting")
    assert len(rows) == 2
    assert rows[0]["content"] == "Thank you for calling"
    assert rows[1]["content"] == "Thanks for calling"
    assert tenant_config["ai_settings"]["voice_id"] == "warm_professional"
    assert v1["id"] != v2["id"]