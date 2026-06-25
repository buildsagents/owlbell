"""
Shared fixtures for orchestrator tests.

Provides common test fixtures for:
- Mock Redis client
- Sample model instances
- Mock dependencies
"""

from __future__ import annotations

import pytest

from backend.orchestrator.models import (
    ActiveSession,
    CallState,
    QueuePriority,
    QueuedCall,
    SystemEvent,
    WorkerNode,
    WorkerStatus,
)


@pytest.fixture
def sample_session() -> ActiveSession:
    """Create a sample ActiveSession for testing."""
    return ActiveSession(
        tenant_id="acme_corp",
        phone_number="+1-555-123-4567",
        caller_number="+1-555-987-6543",
        caller_name="John Doe",
        agent_id="agent-001",
        agent_name="Acme Receptionist",
        state=CallState.ACTIVE,
        worker_id="worker-01:abc123",
        gpu_device=0,
    )


@pytest.fixture
def sample_worker() -> WorkerNode:
    """Create a sample WorkerNode for testing."""
    return WorkerNode(
        worker_id="worker-01:abc123",
        hostname="worker-01",
        ip_address="10.0.0.1",
        pid=1234,
        status=WorkerStatus.IDLE,
        gpu_device=0,
        gpu_name="NVIDIA RTX 4090",
        gpu_memory_total=24576,
        max_concurrent_sessions=4,
        current_sessions=[],
    )


@pytest.fixture
def sample_queued_call() -> QueuedCall:
    """Create a sample QueuedCall for testing."""
    return QueuedCall(
        call_id="call-queued-001",
        tenant_id="acme_corp",
        caller_number="+1-555-111-2222",
        priority=QueuePriority.STANDARD,
    )


@pytest.fixture
def sample_event() -> SystemEvent:
    """Create a sample SystemEvent for testing."""
    return SystemEvent(
        event_type="call_started",
        call_id="call-001",
        tenant_id="acme_corp",
        payload={"caller_number": "+1-555-0000"},
    )
