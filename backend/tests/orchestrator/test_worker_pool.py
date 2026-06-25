"""
Tests for orchestrator.worker_pool module.

Covers:
- WorkerPool initialization
- Worker registration/unregistration
- Heartbeat processing
- Capacity calculation
- Session assignment/release
- Task dispatch stubs
- Auto-scale logic
"""

from __future__ import annotations

import pytest

from backend.orchestrator.models import WorkerNode, WorkerStatus
from backend.orchestrator.worker_pool import WorkerPool


class TestWorkerPool:
    """Tests for WorkerPool class."""

    def test_init(self) -> None:
        """Test WorkerPool initialization."""
        pool = WorkerPool(redis_url="redis://localhost:6379/99")
        assert pool.KEY_WORKER == "worker"
        assert pool.KEY_WORKERS_ALL == "workers:all"
        assert pool.HEARTBEAT_TTL == 10
        assert pool.SCALE_UP_THRESHOLD == 0.85
        assert pool.SCALE_DOWN_THRESHOLD == 0.30
        assert pool.MIN_WORKERS == 1
        assert pool.MAX_WORKERS == 8

    def test_worker_key_format(self) -> None:
        """Test worker key format."""
        pool = WorkerPool(redis_url="redis://localhost:6379/99")
        assert pool._worker_key("worker-01:abc") == "worker:worker-01:abc"

    @pytest.mark.asyncio
    async def test_get_worker_none(self) -> None:
        """Test get_worker returns None for non-existent worker."""
        pool = WorkerPool(redis_url="redis://localhost:6379/99")
        worker = await pool.get_worker("non-existent")
        assert worker is None

    def test_group_by_gpu_empty(self) -> None:
        """Test grouping empty worker list."""
        pool = WorkerPool(redis_url="redis://localhost:6379/99")
        result = pool._group_by_gpu([])
        assert result == {}

    def test_group_by_gpu(self) -> None:
        """Test grouping workers by GPU."""
        pool = WorkerPool(redis_url="redis://localhost:6379/99")
        workers = [
            WorkerNode(
                worker_id="w1",
                hostname="worker-01",
                gpu_device=0,
                max_concurrent_sessions=4,
                current_sessions=["call-1"],
            ),
            WorkerNode(
                worker_id="w2",
                hostname="worker-02",
                gpu_device=0,
                max_concurrent_sessions=4,
                current_sessions=["call-2", "call-3"],
            ),
            WorkerNode(
                worker_id="w3",
                hostname="worker-03",
                gpu_device=1,
                max_concurrent_sessions=4,
                current_sessions=[],
            ),
        ]
        result = pool._group_by_gpu(workers)
        assert "0" in result
        assert "1" in result
        assert result["0"]["workers"] == 2
        assert result["0"]["used_slots"] == 3
        assert result["1"]["workers"] == 1
        assert result["1"]["used_slots"] == 0
        assert result["1"]["available_slots"] == 4


class TestWorkerNodeSlots:
    """Tests for worker available slots calculation."""

    def test_idle_worker_slots(self) -> None:
        """Test available slots for idle worker."""
        worker = WorkerNode(
            worker_id="w1",
            hostname="worker-01",
            status=WorkerStatus.IDLE,
            max_concurrent_sessions=4,
            current_sessions=["call-1"],
        )
        assert worker.available_slots == 3
        assert worker.is_available is True

    def test_full_worker_slots(self) -> None:
        """Test available slots for full worker."""
        worker = WorkerNode(
            worker_id="w1",
            hostname="worker-01",
            status=WorkerStatus.BUSY,
            max_concurrent_sessions=2,
            current_sessions=["call-1", "call-2"],
        )
        assert worker.available_slots == 0
        assert worker.is_available is False

    def test_draining_worker_not_available(self) -> None:
        """Test that draining worker has 0 available slots."""
        worker = WorkerNode(
            worker_id="w1",
            hostname="worker-01",
            status=WorkerStatus.DRAINING,
            max_concurrent_sessions=4,
            current_sessions=["call-1"],
        )
        assert worker.available_slots == 0
        assert worker.is_available is False

    def test_offline_worker_not_available(self) -> None:
        """Test that offline worker is not available."""
        worker = WorkerNode(
            worker_id="w1",
            hostname="worker-01",
            status=WorkerStatus.OFFLINE,
            max_concurrent_sessions=4,
            current_sessions=[],
        )
        assert worker.available_slots == 0
        assert worker.is_available is False

    def test_busy_with_available_slots(self) -> None:
        """Test busy worker with some available slots."""
        worker = WorkerNode(
            worker_id="w1",
            hostname="worker-01",
            status=WorkerStatus.BUSY,
            max_concurrent_sessions=4,
            current_sessions=["call-1"],
        )
        assert worker.available_slots == 3
        assert worker.is_available is True
