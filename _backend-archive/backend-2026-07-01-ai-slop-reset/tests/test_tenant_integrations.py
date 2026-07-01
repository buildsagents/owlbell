"""Tests for tenant_integrations service and Stripe idempotency (Phase 2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.db.tenant_integrations_service import (
    _extract_from_config,
    stripe_event_already_processed,
    upsert_for_tenant,
)


def test_extract_from_config_maps_legacy_keys():
    cfg = {
        "retell_agent_id": "agent_abc",
        "retell_phone": "+15551234567",
        "stripe_customer_id": "cus_123",
        "stripe_subscription_id": "sub_456",
        "stripe_email": "a@b.com",
        "voice_provider": "retell",
    }
    out = _extract_from_config(cfg)
    assert out["retell_agent_id"] == "agent_abc"
    assert out["retell_phone_number"] == "+15551234567"
    assert out["stripe_customer_id"] == "cus_123"


@pytest.mark.asyncio
async def test_upsert_for_tenant_creates_row():
    db = AsyncMock()
    tenant_id = uuid4()

    with patch(
        "backend.db.tenant_integrations_service.get_by_tenant_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        row = await upsert_for_tenant(
            db, tenant_id, retell_agent_id="agent_xyz", stripe_customer_id="cus_99"
        )

    assert row.tenant_id == tenant_id
    assert row.retell_agent_id == "agent_xyz"
    assert row.stripe_customer_id == "cus_99"
    db.add.assert_called_once()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_stripe_event_already_processed_true_when_found():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = object()
    db.execute = AsyncMock(return_value=mock_result)

    assert await stripe_event_already_processed(db, "evt_duplicate") is True


@pytest.mark.asyncio
async def test_stripe_event_already_processed_false_when_missing():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    assert await stripe_event_already_processed(db, "evt_new") is False


@pytest.mark.asyncio
async def test_handle_event_returns_duplicate_without_dispatch():
    from backend.integrations.stripe import service as stripe_service

    mock_db = AsyncMock()
    event = {"id": "evt_1", "type": "invoice.paid", "data": {"object": {}}}

    with patch(
        "backend.db.tenant_integrations_service.stripe_event_already_processed",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await stripe_service.handle_event(event, db=mock_db, event_id="evt_1")

    assert result["action"] == "duplicate"