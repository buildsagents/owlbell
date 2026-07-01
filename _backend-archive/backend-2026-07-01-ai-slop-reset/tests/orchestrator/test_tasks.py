"""
Tests for orchestrator.tasks module.

Covers:
- Task function stubs and signatures
- Utility functions (fallback responses, disposition)
- Circuit breaker integration in tasks
- Task dispatch wrappers
"""

from __future__ import annotations

import pytest

from backend.orchestrator.models import ActiveSession
from backend.orchestrator.tasks import (
    _get_fallback_response,
    determine_disposition,
)


class TestFallbackResponses:
    """Tests for fallback response utility."""

    def test_default_fallbacks(self) -> None:
        """Test that default fallbacks are returned."""
        response = _get_fallback_response({})
        assert isinstance(response, str)
        assert len(response) > 0

    def test_custom_fallbacks(self) -> None:
        """Test that custom fallbacks from agent_config are used."""
        custom = ["Custom fallback 1", "Custom fallback 2"]
        response = _get_fallback_response({"fallback_responses": custom})
        assert response in custom

    def test_fallback_not_empty(self) -> None:
        """Test that fallback response is never empty."""
        for _ in range(20):
            response = _get_fallback_response({})
            assert len(response) > 0


class TestDetermineDisposition:
    """Tests for determine_disposition function."""

    def test_completed_call(self) -> None:
        """Test disposition for completed call."""
        from datetime import datetime, timedelta
        session = ActiveSession(
            tenant_id="t1",
            phone_number="+1-555-0000",
            caller_number="+1-555-1111",
            agent_id="a1",
            answered_at=datetime.utcnow() - timedelta(seconds=60),
            ended_at=datetime.utcnow(),
        )
        assert determine_disposition(session) == "completed"

    def test_abandoned_call(self) -> None:
        """Test disposition for abandoned call (< 5s)."""
        from datetime import datetime, timedelta
        session = ActiveSession(
            tenant_id="t1",
            phone_number="+1-555-0000",
            caller_number="+1-555-1111",
            agent_id="a1",
            answered_at=datetime.utcnow() - timedelta(seconds=2),
            ended_at=datetime.utcnow(),
        )
        assert determine_disposition(session) == "abandoned"

    def test_error_call(self) -> None:
        """Test disposition for call with many errors."""
        session = ActiveSession(
            tenant_id="t1",
            phone_number="+1-555-0000",
            caller_number="+1-555-1111",
            agent_id="a1",
            error_count=10,
        )
        assert determine_disposition(session) == "error"

    def test_missed_call(self) -> None:
        """Test disposition for missed call (never answered)."""
        from datetime import datetime
        session = ActiveSession(
            tenant_id="t1",
            phone_number="+1-555-0000",
            caller_number="+1-555-1111",
            agent_id="a1",
            ended_at=datetime.utcnow(),
        )
        assert determine_disposition(session) == "missed"

    def test_missed_disposition(self) -> None:
        """Test disposition for missed call (never answered)."""
        session = ActiveSession(
            tenant_id="t1",
            phone_number="+1-555-0000",
            caller_number="+1-555-1111",
            agent_id="a1",
        )
        # No ended_at, no answered_at -> missed (call was never completed)
        assert determine_disposition(session) == "missed"
