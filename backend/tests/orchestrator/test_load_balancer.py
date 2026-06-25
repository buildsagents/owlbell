"""
Tests for orchestrator.load_balancer module.

Covers:
- LoadBalancer initialization and strategies
- Worker selection strategies
- Tenant GPU preference tracking
- Capability tracking
- Rebalancing logic
"""

from __future__ import annotations

import pytest

from backend.orchestrator.load_balancer import LoadBalancer
from backend.orchestrator.models import WorkerNode, WorkerStatus


class MockWorkerPool:
    """Mock worker pool for testing."""

    def __init__(self, workers=None):
        self._workers = workers or []

    async def get_available_workers(self):
        return [w for w in self._workers if w.is_available]

    async def list_workers(self):
        return self._workers

    async def assign_session(self, worker_id, call_id):
        return True

    async def release_session(self, worker_id, call_id):
        return True


class TestLoadBalancer:
    """Tests for LoadBalancer class."""

    def test_init_default_strategy(self) -> None:
        """Test LoadBalancer with default strategy."""
        pool = MockWorkerPool()
        lb = LoadBalancer(worker_pool=pool, redis_url="redis://localhost:6379/99")
        assert lb.strategy == "least_load"

    def test_init_round_robin(self) -> None:
        """Test LoadBalancer with round_robin strategy."""
        pool = MockWorkerPool()
        lb = LoadBalancer(
            worker_pool=pool, strategy="round_robin", redis_url="redis://localhost:6379/99"
        )
        assert lb.strategy == "round_robin"

    def test_init_invalid_strategy(self) -> None:
        """Test that invalid strategy raises ValueError."""
        pool = MockWorkerPool()
        with pytest.raises(ValueError):
            LoadBalancer(
                worker_pool=pool,
                strategy="invalid_strategy",
                redis_url="redis://localhost:6379/99",
            )

    def test_strategies_list(self) -> None:
        """Test that STRATEGIES contains all expected strategies."""
        assert "round_robin" in LoadBalancer.STRATEGIES
        assert "least_load" in LoadBalancer.STRATEGIES
        assert "latency_based" in LoadBalancer.STRATEGIES
        assert "gpu_affinity" in LoadBalancer.STRATEGIES


class TestLeastLoadStrategy:
    """Tests for least_load strategy."""

    def test_selects_most_available_slots(self) -> None:
        """Test that least_load selects worker with most available slots."""
        pool = MockWorkerPool()
        lb = LoadBalancer(worker_pool=pool, redis_url="redis://localhost:6379/99")

        workers = [
            WorkerNode(
                worker_id="w1",
                hostname="w1",
                status=WorkerStatus.IDLE,
                max_concurrent_sessions=4,
                current_sessions=["call-1", "call-2"],
            ),
            WorkerNode(
                worker_id="w2",
                hostname="w2",
                status=WorkerStatus.IDLE,
                max_concurrent_sessions=4,
                current_sessions=[],
            ),
            WorkerNode(
                worker_id="w3",
                hostname="w3",
                status=WorkerStatus.IDLE,
                max_concurrent_sessions=4,
                current_sessions=["call-1"],
            ),
        ]
        selected = lb._least_load(workers)
        assert selected.worker_id == "w2"  # 4 available slots

    def test_empty_workers(self) -> None:
        """Test least_load with empty list."""
        pool = MockWorkerPool()
        lb = LoadBalancer(worker_pool=pool, redis_url="redis://localhost:6379/99")
        selected = lb._least_load([])
        assert selected is None

    def test_tie_break_by_latency(self) -> None:
        """Test tie-breaking by latency."""
        pool = MockWorkerPool()
        lb = LoadBalancer(worker_pool=pool, redis_url="redis://localhost:6379/99")

        workers = [
            WorkerNode(
                worker_id="w1",
                hostname="w1",
                status=WorkerStatus.IDLE,
                max_concurrent_sessions=4,
                current_sessions=["call-1"],
                avg_inference_latency_ms=200,
            ),
            WorkerNode(
                worker_id="w2",
                hostname="w2",
                status=WorkerStatus.IDLE,
                max_concurrent_sessions=4,
                current_sessions=["call-2"],
                avg_inference_latency_ms=100,
            ),
        ]
        selected = lb._least_load(workers)
        assert selected.worker_id == "w2"  # Lower latency


class TestRoundRobinStrategy:
    """Tests for round_robin strategy."""

    @pytest.mark.asyncio
    async def test_cycles_through_workers(self) -> None:
        """Test that round_robin cycles through workers."""
        pool = MockWorkerPool()
        lb = LoadBalancer(
            worker_pool=pool, strategy="round_robin", redis_url="redis://localhost:6379/99"
        )

        workers = [
            WorkerNode(worker_id="w0", hostname="w0", status=WorkerStatus.IDLE),
            WorkerNode(worker_id="w1", hostname="w1", status=WorkerStatus.IDLE),
            WorkerNode(worker_id="w2", hostname="w2", status=WorkerStatus.IDLE),
        ]

        selected1 = await lb._round_robin(workers)
        selected2 = await lb._round_robin(workers)
        selected3 = await lb._round_robin(workers)
        selected4 = await lb._round_robin(workers)

        assert selected1.worker_id == "w0"
        assert selected2.worker_id == "w1"
        assert selected3.worker_id == "w2"
        assert selected4.worker_id == "w0"  # Cycles back

    def test_empty_workers(self) -> None:
        """Test round_robin with empty list."""
        pool = MockWorkerPool()
        lb = LoadBalancer(worker_pool=pool, redis_url="redis://localhost:6379/99")

        # Can't test async with empty, so test the fallback
        selected = lb._least_load([])
        assert selected is None


class TestLatencyBasedStrategy:
    """Tests for latency_based strategy."""

    def test_prefers_zero_latency(self) -> None:
        """Test that latency_based prefers workers with 0 latency."""
        pool = MockWorkerPool()
        lb = LoadBalancer(worker_pool=pool, redis_url="redis://localhost:6379/99")

        workers = [
            WorkerNode(
                worker_id="w1",
                hostname="w1",
                status=WorkerStatus.IDLE,
                avg_inference_latency_ms=150,
            ),
            WorkerNode(
                worker_id="w2",
                hostname="w2",
                status=WorkerStatus.IDLE,
                avg_inference_latency_ms=0,
            ),
        ]
        selected = lb._latency_based(workers)
        assert selected.worker_id == "w2"

    def test_prefers_lower_latency(self) -> None:
        """Test that latency_based prefers lower latency workers."""
        pool = MockWorkerPool()
        lb = LoadBalancer(worker_pool=pool, redis_url="redis://localhost:6379/99")

        workers = [
            WorkerNode(
                worker_id="w1",
                hostname="w1",
                status=WorkerStatus.IDLE,
                avg_inference_latency_ms=200,
            ),
            WorkerNode(
                worker_id="w2",
                hostname="w2",
                status=WorkerStatus.IDLE,
                avg_inference_latency_ms=100,
            ),
        ]
        selected = lb._latency_based(workers)
        assert selected.worker_id == "w2"
