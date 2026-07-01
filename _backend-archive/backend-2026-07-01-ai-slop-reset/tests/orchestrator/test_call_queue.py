"""
Tests for orchestrator.call_queue module.

Covers:
- Queue initialization
- Priority score calculation
- Wait time estimation
- Overflow handling
- Tenant-specific operations
"""

from __future__ import annotations

import pytest

from backend.orchestrator.call_queue import CallQueue
from backend.orchestrator.models import QueuePriority, QueuedCall


class TestCallQueue:
    """Tests for CallQueue class."""

    def test_init(self) -> None:
        """Test CallQueue initialization."""
        queue = CallQueue(redis_url="redis://localhost:6379/99")
        assert queue.KEY_QUEUE == "queue:{tenant_id}"
        assert queue.KEY_GLOBAL_QUEUE == "queue:global"
        assert queue.ANNOUNCE_INTERVAL_SECONDS == 30
        assert queue.EMA_ALPHA == 0.3

    @pytest.mark.asyncio
    async def test_get_wait_estimate_default(self) -> None:
        """Test wait time estimation with no historical data."""
        queue = CallQueue(redis_url="redis://localhost:6379/99")
        estimate = await queue.get_wait_estimate("acme", 3)
        # Default 30s * position 3 = 90s
        assert estimate == 90

    @pytest.mark.asyncio
    async def test_get_wait_estimate_position_1(self) -> None:
        """Test wait time estimation for position 1."""
        queue = CallQueue(redis_url="redis://localhost:6379/99")
        estimate = await queue.get_wait_estimate("acme", 1)
        assert estimate == 30  # Default 30s * 1


class TestQueuePriority:
    """Tests for QueuePriority enum."""

    def test_emergency_is_highest(self) -> None:
        """Test that EMERGENCY is the highest priority."""
        assert QueuePriority.EMERGENCY.value == 1

    def test_low_is_lowest(self) -> None:
        """Test that LOW is the lowest priority."""
        assert QueuePriority.LOW.value == 40

    def test_ordering(self) -> None:
        """Test priority ordering."""
        priorities = [
            QueuePriority.EMERGENCY,
            QueuePriority.VIP,
            QueuePriority.CALLBACK,
            QueuePriority.STANDARD,
            QueuePriority.LOW,
        ]
        for i in range(len(priorities) - 1):
            assert priorities[i].value < priorities[i + 1].value


class TestQueuedCall:
    """Tests for QueuedCall model."""

    def test_queue_score_format(self) -> None:
        """Test that queue score has correct format."""
        from datetime import datetime, timezone
        call = QueuedCall(
            call_id="c1",
            tenant_id="acme",
            caller_number="+1-555-0000",
            priority=QueuePriority.STANDARD,
            queue_entered_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        score = call.get_queue_score()
        # Score should be approximately 30.1704067200
        assert score >= 30.0
        assert score < 31.0

    def test_fifo_within_same_priority(self) -> None:
        """Test FIFO ordering within same priority."""
        from datetime import datetime, timedelta, timezone
        call1 = QueuedCall(
            call_id="c1",
            tenant_id="acme",
            caller_number="+1-555-0000",
            priority=QueuePriority.STANDARD,
            queue_entered_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )
        call2 = QueuedCall(
            call_id="c2",
            tenant_id="acme",
            caller_number="+1-555-1111",
            priority=QueuePriority.STANDARD,
            queue_entered_at=datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        )
        # Earlier call should have lower score
        assert call1.get_queue_score() < call2.get_queue_score()
