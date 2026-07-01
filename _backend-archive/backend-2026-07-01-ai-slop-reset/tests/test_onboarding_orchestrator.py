"""Tests for unified onboarding orchestrator (Phase 3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from backend.domain.onboarding.orchestrator import OnboardingOrchestrator
from backend.domain.onboarding.steps import (
    STEP_INTAKE_SUBMITTED,
    STEP_PAYMENT_RECEIVED,
    STEP_PHONE_PROVISIONED,
    STEP_RETELL_PROVISIONED,
)

pytestmark = pytest.mark.unit


def _mock_session_maker():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=session)


@pytest.mark.asyncio
async def test_on_checkout_completed_creates_pipeline_and_completes_welcome():
    sm = _mock_session_maker()
    orch = OnboardingOrchestrator(sm)
    tenant_id = str(uuid4())

    with patch("backend.domain.onboarding.orchestrator.automation.get_pipeline", new_callable=AsyncMock, return_value=None):
        with patch("backend.domain.onboarding.orchestrator.automation.create_pipeline", new_callable=AsyncMock) as create:
            create.return_value = MagicMock(id="pipe-1")
            with patch("backend.domain.onboarding.orchestrator.email_sequence.create_sequence", new_callable=AsyncMock):
                with patch("backend.domain.onboarding.orchestrator.automation.complete_step", new_callable=AsyncMock) as complete:
                    result = await orch.on_checkout_completed(
                        tenant_id=tenant_id,
                        email="test@example.com",
                        business_name="Test Plumbing",
                    )

    complete.assert_awaited_once_with(
        sm, tenant_id, STEP_PAYMENT_RECEIVED,
        notes="Payment received via Stripe checkout",
    )
    assert result["pipeline_created"] is True


@pytest.mark.asyncio
async def test_on_intake_submitted_schedules_provision():
    sm = _mock_session_maker()
    orch = OnboardingOrchestrator(sm)
    tenant_id = str(uuid4())

    with patch("backend.domain.onboarding.orchestrator.automation.get_pipeline", new_callable=AsyncMock, return_value=MagicMock()):
        with patch("backend.domain.onboarding.orchestrator.automation.complete_step", new_callable=AsyncMock, return_value={"success": True}):
            with patch.object(orch, "_schedule_provision", return_value=True) as schedule:
                result = await orch.on_intake_submitted(tenant_id=tenant_id, intake_payload={"trade": "Plumbing"})

    schedule.assert_called_once()
    assert result["provision_scheduled"] is True


@pytest.mark.asyncio
async def test_on_provision_complete_advances_ai_and_phone_steps():
    sm = _mock_session_maker()
    orch = OnboardingOrchestrator(sm)
    tenant_id = str(uuid4())

    with patch("backend.domain.onboarding.orchestrator.automation.complete_step", new_callable=AsyncMock, return_value={"success": True}) as complete:
        result = await orch.on_provision_complete(
            tenant_id=tenant_id,
            result={"status": "complete", "retell_agent_id": "agent_1", "retell_phone_number": "+15551234567"},
        )

    assert complete.await_count == 2
    assert complete.await_args_list[0].args[2] == STEP_RETELL_PROVISIONED
    assert complete.await_args_list[1].args[2] == STEP_PHONE_PROVISIONED
    assert result["success"] is True