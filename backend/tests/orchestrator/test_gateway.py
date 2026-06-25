"""
Tests for orchestrator.gateway module.

Covers:
- GatewayRouter initialization
- Router creation
- Call duration calculation
- Helper method functionality
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.orchestrator.gateway import GatewayRouter, create_orchestrator_router
from backend.orchestrator.models import ActiveSession, CallState


class MockManager:
    """Mock manager for testing."""

    def __init__(self):
        self.sessions = {}

    async def get_session(self, call_id):
        return self.sessions.get(call_id)

    async def list_sessions(self, **kwargs):
        return list(self.sessions.values())

    async def count_sessions(self, **kwargs):
        return len(self.sessions)

    async def update_session(self, call_id, updates):
        if call_id in self.sessions:
            for k, v in updates.items():
                setattr(self.sessions[call_id], k, v)


class MockWorkerPool:
    """Mock worker pool."""

    async def drain_worker(self, worker_id):
        return True

    async def restart_worker(self, worker_id):
        return {"status": "restarted"}

    async def list_workers(self):
        return []

    async def get_worker(self, worker_id):
        return None

    def process_audio_chunk(self, call_id, audio):
        return None

    def handle_call_end(self, call_id):
        return None

    async def release_worker(self, worker_id, call_id):
        return True


class MockEventBus:
    """Mock event bus."""

    def publish(self, event):
        pass

    async def get_recent_events(self, event_type=None, limit=100):
        return []

    async def get_stream_events(self, start_id="0", count=100):
        return []

    async def subscribe(self, **kwargs):
        return
        yield


class MockLoadBalancer:
    """Mock load balancer."""

    pass


class MockHealthMonitor:
    """Mock health monitor."""

    async def get_system_status(self):
        return {"status": "healthy"}

    async def get_prometheus_metrics(self):
        return ""

    async def get_aggregate_stats(self):
        return {}


class MockCallQueue:
    """Mock call queue."""

    async def get_global_status(self):
        return {"total_queued": 0}

    async def get_tenant_queue(self, tenant_id):
        return {"tenant_id": tenant_id, "count": 0}

    async def update_priority(self, call_id, priority):
        return True


def create_test_gateway():
    """Create a GatewayRouter with all mocks."""
    return GatewayRouter(
        session_manager=MockManager(),
        worker_pool=MockWorkerPool(),
        event_bus=MockEventBus(),
        load_balancer=MockLoadBalancer(),
        health_monitor=MockHealthMonitor(),
        call_queue=MockCallQueue(),
    )


class TestGatewayRouter:
    """Tests for GatewayRouter."""

    def test_init(self) -> None:
        """Test GatewayRouter initialization."""
        gateway = create_test_gateway()
        assert gateway.session_mgr is not None
        assert gateway.worker_pool is not None
        assert gateway.event_bus is not None
        assert gateway.active_connections == {}
        assert gateway.active_tasks == {}

    def test_get_router(self) -> None:
        """Test that get_router creates an APIRouter."""
        gateway = create_test_gateway()
        router = gateway.get_router()
        assert router is not None

    def test_create_orchestrator_router(self) -> None:
        """Test the factory function."""
        router = create_orchestrator_router(
            session_manager=MockManager(),
            worker_pool=MockWorkerPool(),
            event_bus=MockEventBus(),
            load_balancer=MockLoadBalancer(),
            health_monitor=MockHealthMonitor(),
            call_queue=MockCallQueue(),
        )
        assert router is not None

    def test_get_call_duration(self) -> None:
        """Test call duration calculation."""
        now = datetime.utcnow()
        session = ActiveSession(
            tenant_id="t1",
            phone_number="+1-555-0000",
            caller_number="+1-555-1111",
            agent_id="a1",
            answered_at=now - timedelta(seconds=125),
            ended_at=now,
        )
        duration = GatewayRouter._get_call_duration(session)
        assert duration == 125

    def test_get_call_duration_no_ended(self) -> None:
        """Test duration when call hasn't ended."""
        session = ActiveSession(
            tenant_id="t1",
            phone_number="+1-555-0000",
            caller_number="+1-555-1111",
            agent_id="a1",
        )
        duration = GatewayRouter._get_call_duration(session)
        assert duration == 0

    def test_get_call_duration_no_answered(self) -> None:
        """Test duration when call was never answered."""
        now = datetime.utcnow()
        session = ActiveSession(
            tenant_id="t1",
            phone_number="+1-555-0000",
            caller_number="+1-555-1111",
            agent_id="a1",
            ended_at=now,
        )
        duration = GatewayRouter._get_call_duration(session)
        assert duration == 0
