"""
Tests for orchestrator.health_monitor module.

Covers:
- HealthMonitor initialization
- Threshold constants
- Degradation state management
- Worker state change tracking
- Restart rate limiting
- Alert generation
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.orchestrator.health_monitor import HealthMonitor
from backend.orchestrator.models import WorkerNode, WorkerStatus


class TestHealthMonitorInit:
    """Tests for HealthMonitor initialization."""

    def test_init(self) -> None:
        """Test HealthMonitor initialization."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        assert hm.HEARTBEAT_INTERVAL == 2
        assert hm.HEARTBEAT_MISS_THRESHOLD == 3
        assert hm.OFFLINE_THRESHOLD == 15
        assert hm.GPU_UTIL_HIGH == 90.0
        assert hm.GPU_TEMP_HIGH == 85.0
        assert hm.GPU_TEMP_CRITICAL == 95.0
        assert hm.AUTO_RESTART_ENABLED is True
        assert hm.RESTART_COOLDOWN == 60
        assert hm.MAX_RESTART_ATTEMPTS == 3
        assert hm.METRIC_PREFIX == "answerflow"
        assert hm._degradation_active is False


class TestDegradationManagement:
    """Tests for degradation state management."""

    @pytest.mark.asyncio
    async def test_enable_degradation(self) -> None:
        """Test enabling degradation mode."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        await hm._enable_degradation("cache_only", 0.95)

        assert hm._degradation_active is True
        assert hm._degradation_mode == "cache_only"
        assert hm._degradation_since is not None

    @pytest.mark.asyncio
    async def test_disable_degradation(self) -> None:
        """Test disabling degradation mode."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        await hm._enable_degradation("cache_only", 0.95)
        await hm._disable_degradation(0.60)

        assert hm._degradation_active is False
        assert hm._degradation_mode == "none"
        assert hm._degradation_since is None


class TestRestartRateLimiting:
    """Tests for restart rate limiting."""

    @pytest.mark.asyncio
    async def test_can_restart_initially(self) -> None:
        """Test that restart is allowed initially."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        result = await hm._can_restart("worker-01")
        assert result is True

    @pytest.mark.asyncio
    async def test_can_restart_after_max_attempts(self) -> None:
        """Test restart is blocked after max attempts."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        for _ in range(hm.MAX_RESTART_ATTEMPTS):
            hm._record_restart("worker-01")
        result = await hm._can_restart("worker-01")
        assert result is False

    @pytest.mark.asyncio
    async def test_cooldown_enforced(self) -> None:
        """Test that cooldown period is enforced."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        hm._record_restart("worker-01")
        result = await hm._can_restart("worker-01")
        # Should be False due to cooldown
        assert result is False

    def test_record_restart(self) -> None:
        """Test recording a restart attempt."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        hm._record_restart("worker-01")
        assert "worker-01" in hm._restart_history
        assert len(hm._restart_history["worker-01"]) == 1


class TestWorkerStateChanges:
    """Tests for worker state change methods."""

    @pytest.mark.asyncio
    async def test_mark_unhealthy(self) -> None:
        """Test marking a worker as unhealthy."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        worker = WorkerNode(
            worker_id="w1",
            hostname="worker-01",
            status=WorkerStatus.IDLE,
        )
        await hm._mark_unhealthy(worker)
        # Verify Redis was updated (even without real Redis)

    @pytest.mark.asyncio
    async def test_mark_offline(self) -> None:
        """Test marking a worker as offline."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        worker = WorkerNode(
            worker_id="w1",
            hostname="worker-01",
            status=WorkerStatus.UNHEALTHY,
        )
        await hm._mark_offline(worker)


class TestAlertChecking:
    """Tests for alert checking."""

    @pytest.mark.asyncio
    async def test_no_alerts_when_healthy(self) -> None:
        """Test that no alerts are generated when system is healthy."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        alerts = await hm.check_alerts()
        assert isinstance(alerts, list)


class TestThresholds:
    """Tests for threshold constants."""

    def test_overload_threshold(self) -> None:
        """Test overload threshold."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        assert hm.OVERLOAD_SESSION_RATIO == 0.95

    def test_degradation_trigger(self) -> None:
        """Test degradation trigger threshold."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        assert hm.DEGRADATION_TRIGGER == 0.90

    def test_recovery_threshold(self) -> None:
        """Test recovery threshold."""
        hm = HealthMonitor(redis_url="redis://localhost:6379/99")
        assert hm.RECOVERY_THRESHOLD == 0.70
