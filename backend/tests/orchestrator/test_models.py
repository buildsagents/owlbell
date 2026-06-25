"""
Tests for orchestrator.models module.

Covers all Pydantic models:
- ActiveSession: serialization, deserialization, Redis round-trip
- WorkerNode: serialization, available_slots calculation
- QueuedCall: queue score calculation
- SystemEvent: JSON serialization
- WebSocket message models
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

import pytest

from backend.orchestrator.models import (
    ActiveSession,
    AudioInputMessage,
    AudioOutputMessage,
    CallState,
    ControlMessage,
    ErrorMessage,
    EventType,
    QueuePriority,
    QueuedCall,
    StatusMessage,
    SystemEvent,
    TranscriptMessage,
    WorkerNode,
    WorkerStatus,
)


class TestActiveSession:
    """Tests for ActiveSession model."""

    def test_create_default(self) -> None:
        """Test creating a session with defaults."""
        session = ActiveSession(
            tenant_id="acme_corp",
            phone_number="+1-555-123-4567",
            caller_number="+1-555-987-6543",
            agent_id="agent-001",
        )
        assert session.tenant_id == "acme_corp"
        assert session.state == CallState.CREATED
        assert session.call_id is not None
        assert len(session.call_id) > 0
        assert session.created_at is not None
        assert session.audio_chunks_received == 0

    def test_call_state_values(self) -> None:
        """Test all CallState enum values."""
        assert CallState.CREATED == "created"
        assert CallState.QUEUED == "queued"
        assert CallState.ASSIGNED == "assigned"
        assert CallState.CONNECTING == "connecting"
        assert CallState.ACTIVE == "active"
        assert CallState.PROCESSING == "processing"
        assert CallState.HOLDING == "holding"
        assert CallState.ENDED == "ended"
        assert CallState.ARCHIVED == "archived"

    def test_to_redis_hash(self) -> None:
        """Test serialization to Redis hash."""
        session = ActiveSession(
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
        hash_data = session.to_redis_hash()

        assert hash_data["tenant_id"] == "acme_corp"
        assert hash_data["state"] == "active"
        assert hash_data["caller_name"] == "John Doe"
        assert hash_data["worker_id"] == "worker-01:abc123"
        assert hash_data["gpu_device"] == "0"
        assert hash_data["ws_connected"] == "0"

    def test_from_redis_hash(self) -> None:
        """Test deserialization from Redis hash."""
        hash_data = {
            "call_id": "550e8400-e29b-41d4-a716-446655440000",
            "tenant_id": "acme_corp",
            "phone_number": "+1-555-123-4567",
            "caller_number": "+1-555-987-6543",
            "caller_name": "Jane Smith",
            "state": "active",
            "state_history": "[]",
            "created_at": datetime.utcnow().isoformat(),
            "answered_at": "",
            "ended_at": "",
            "last_activity_at": datetime.utcnow().isoformat(),
            "worker_id": "worker-02:def456",
            "worker_node": "worker-02",
            "gpu_device": "1",
            "queue_position": "",
            "queue_entered_at": "",
            "agent_id": "agent-002",
            "agent_name": "Beta Agent",
            "agent_config": "{}",
            "transcript": "[]",
            "current_utterance": "",
            "audio_chunks_received": "10",
            "audio_chunks_sent": "5",
            "llm_calls": "3",
            "stt_calls": "8",
            "tts_calls": "3",
            "total_audio_seconds": "120.5",
            "mos_score": "",
            "error_count": "0",
            "last_error": "",
            "ws_connected": "1",
            "ws_client_ip": "192.168.1.100",
        }
        session = ActiveSession.from_redis_hash(hash_data)

        assert session.call_id == "550e8400-e29b-41d4-a716-446655440000"
        assert session.tenant_id == "acme_corp"
        assert session.state == CallState.ACTIVE
        assert session.caller_name == "Jane Smith"
        assert session.worker_id == "worker-02:def456"
        assert session.gpu_device == 1
        assert session.ws_connected is True
        assert session.ws_client_ip == "192.168.1.100"
        assert session.audio_chunks_received == 10
        assert session.total_audio_seconds == 120.5

    def test_round_trip(self) -> None:
        """Test Redis hash round-trip serialization."""
        original = ActiveSession(
            tenant_id="test_tenant",
            phone_number="+1-555-000-0000",
            caller_number="+1-555-111-1111",
            caller_name="Test Caller",
            agent_id="agent-test",
            agent_name="Test Agent",
            state=CallState.PROCESSING,
            worker_id="worker-test:123",
            gpu_device=2,
            transcript=[
                {"speaker": "caller", "text": "Hello", "timestamp": "2024-01-01T00:00:00"}
            ],
            audio_chunks_received=42,
            llm_calls=5,
        )
        hash_data = original.to_redis_hash()
        restored = ActiveSession.from_redis_hash(hash_data)

        assert restored.tenant_id == original.tenant_id
        assert restored.state == original.state
        assert restored.caller_name == original.caller_name
        assert restored.worker_id == original.worker_id
        assert restored.gpu_device == original.gpu_device
        assert restored.audio_chunks_received == original.audio_chunks_received
        assert len(restored.transcript) == 1

    def test_transcript_json_serialization(self) -> None:
        """Test transcript serialization in Redis hash."""
        session = ActiveSession(
            tenant_id="t1",
            phone_number="+1-555-0000",
            caller_number="+1-555-1111",
            agent_id="a1",
            transcript=[
                {
                    "speaker": "caller",
                    "text": "Hello",
                    "timestamp": "2024-01-01T00:00:00",
                },
                {
                    "speaker": "agent",
                    "text": "Hi there!",
                    "timestamp": "2024-01-01T00:00:01",
                },
            ],
        )
        hash_data = session.to_redis_hash()
        transcript_json = json.loads(hash_data["transcript"])
        assert len(transcript_json) == 2
        assert transcript_json[0]["speaker"] == "caller"

    def test_json_serialization(self) -> None:
        """Test JSON serialization for API responses."""
        session = ActiveSession(
            tenant_id="acme",
            phone_number="+1-555-0000",
            caller_number="+1-555-1111",
            agent_id="a1",
            state=CallState.ACTIVE,
        )
        data = session.model_dump(mode="json")
        assert data["tenant_id"] == "acme"
        assert data["state"] == "active"
        assert "created_at" in data


class TestWorkerNode:
    """Tests for WorkerNode model."""

    def test_create_default(self) -> None:
        """Test creating a worker with defaults."""
        worker = WorkerNode(
            worker_id="worker-01:abc123",
            hostname="worker-01",
            status=WorkerStatus.IDLE,
        )
        assert worker.worker_id == "worker-01:abc123"
        assert worker.status == WorkerStatus.IDLE
        assert worker.gpu_device == 0
        assert worker.max_concurrent_sessions == 4
        assert worker.available_slots == 4

    def test_worker_status_values(self) -> None:
        """Test all WorkerStatus enum values."""
        assert WorkerStatus.STARTING == "starting"
        assert WorkerStatus.IDLE == "idle"
        assert WorkerStatus.BUSY == "busy"
        assert WorkerStatus.DRAINING == "draining"
        assert WorkerStatus.UNHEALTHY == "unhealthy"
        assert WorkerStatus.OFFLINE == "offline"

    def test_available_slots_idle(self) -> None:
        """Test available_slots when worker is idle."""
        worker = WorkerNode(
            worker_id="w1",
            hostname="worker-01",
            status=WorkerStatus.IDLE,
            max_concurrent_sessions=4,
            current_sessions=["call-1", "call-2"],
        )
        assert worker.available_slots == 2
        assert worker.is_available is True

    def test_available_slots_busy(self) -> None:
        """Test available_slots when worker is busy."""
        worker = WorkerNode(
            worker_id="w1",
            hostname="worker-01",
            status=WorkerStatus.BUSY,
            max_concurrent_sessions=4,
            current_sessions=["call-1", "call-2", "call-3", "call-4"],
        )
        assert worker.available_slots == 0
        assert worker.is_available is False

    def test_available_slots_unhealthy(self) -> None:
        """Test available_slots when worker is unhealthy."""
        worker = WorkerNode(
            worker_id="w1",
            hostname="worker-01",
            status=WorkerStatus.UNHEALTHY,
            max_concurrent_sessions=4,
            current_sessions=["call-1"],
        )
        assert worker.available_slots == 0
        assert worker.is_available is False

    def test_redis_round_trip(self) -> None:
        """Test Redis hash round-trip for worker."""
        original = WorkerNode(
            worker_id="worker-01:abc123",
            hostname="worker-01",
            ip_address="10.0.0.1",
            pid=1234,
            status=WorkerStatus.BUSY,
            gpu_device=0,
            gpu_name="NVIDIA RTX 4090",
            gpu_memory_total=24576,
            gpu_memory_free=8192,
            supported_models=["whisper-large", "llama-7b"],
            current_sessions=["call-1", "call-2"],
            max_concurrent_sessions=4,
            cpu_percent=45.2,
            memory_percent=62.1,
            gpu_utilization=78.5,
            gpu_memory_used=16384,
            avg_inference_latency_ms=145.2,
            total_requests_served=1024,
            errors_count=3,
            version="1.0.1",
        )
        hash_data = original.to_redis_hash()
        restored = WorkerNode.from_redis_hash(hash_data)

        assert restored.worker_id == original.worker_id
        assert restored.status == original.status
        assert restored.gpu_memory_total == 24576
        assert restored.current_sessions == ["call-1", "call-2"]
        assert restored.supported_models == ["whisper-large", "llama-7b"]
        assert restored.version == "1.0.1"


class TestQueuedCall:
    """Tests for QueuedCall model."""

    def test_create_default(self) -> None:
        """Test creating a queued call with defaults."""
        call = QueuedCall(
            call_id="call-001",
            tenant_id="acme_corp",
            caller_number="+1-555-1234",
        )
        assert call.priority == QueuePriority.STANDARD
        assert call.position == 0
        assert call.queue_reason == "no_workers_available"

    def test_queue_priority_values(self) -> None:
        """Test all QueuePriority enum values."""
        assert QueuePriority.EMERGENCY == 1
        assert QueuePriority.VIP == 10
        assert QueuePriority.CALLBACK == 20
        assert QueuePriority.STANDARD == 30
        assert QueuePriority.LOW == 40

    def test_get_queue_score(self) -> None:
        """Test queue score calculation."""
        from datetime import datetime, timezone
        call = QueuedCall(
            call_id="call-001",
            tenant_id="acme",
            caller_number="+1-555-0000",
            priority=QueuePriority.VIP,
            queue_entered_at=datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        )
        score = call.get_queue_score()
        # Score format: priority.timestamp
        assert score < 20.0  # Should be around 10.{timestamp}
        assert score >= 10.0

    def test_vip_has_lower_score_than_standard(self) -> None:
        """Test that VIP calls have lower scores (higher priority)."""
        from datetime import datetime, timezone
        vip = QueuedCall(
            call_id="vip-001",
            tenant_id="acme",
            caller_number="+1-555-0000",
            priority=QueuePriority.VIP,
            queue_entered_at=datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        )
        standard = QueuedCall(
            call_id="std-001",
            tenant_id="acme",
            caller_number="+1-555-1111",
            priority=QueuePriority.STANDARD,
            queue_entered_at=datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        )
        assert vip.get_queue_score() < standard.get_queue_score()


class TestSystemEvent:
    """Tests for SystemEvent model."""

    def test_create_default(self) -> None:
        """Test creating an event with defaults."""
        event = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id="call-001",
            tenant_id="acme",
        )
        assert event.event_type == EventType.CALL_STARTED
        assert event.call_id == "call-001"
        assert event.tenant_id == "acme"
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.source == "orchestrator"
        assert event.version == "1.0.0"

    def test_event_type_values(self) -> None:
        """Test key EventType enum values."""
        assert EventType.CALL_STARTED == "call_started"
        assert EventType.CALL_ENDED == "call_ended"
        assert EventType.TRANSCRIPT_READY == "transcript_ready"
        assert EventType.WORKER_UNHEALTHY == "worker_unhealthy"
        assert EventType.SYSTEM_OVERLOAD == "system_overload"
        assert EventType.ERROR_LLM_TIMEOUT == "error_llm_timeout"

    def test_to_json(self) -> None:
        """Test JSON serialization."""
        event = SystemEvent(
            event_type=EventType.CALL_STARTED,
            call_id="call-001",
            tenant_id="acme",
            payload={"caller": "+1-555-0000"},
        )
        json_str = event.to_json()
        data = json.loads(json_str)
        assert data["event_type"] == "call_started"
        assert data["call_id"] == "call-001"
        assert data["payload"]["caller"] == "+1-555-0000"

    def test_from_json(self) -> None:
        """Test JSON deserialization."""
        event = SystemEvent(
            event_type=EventType.CALL_ENDED,
            call_id="call-002",
            tenant_id="acme",
            payload={"duration": 120, "reason": "hangup"},
        )
        json_str = event.to_json()
        restored = SystemEvent.from_json(json_str)
        assert restored.event_type == EventType.CALL_ENDED
        assert restored.call_id == "call-002"
        assert restored.payload["duration"] == 120

    def test_json_round_trip(self) -> None:
        """Test JSON round-trip serialization."""
        original = SystemEvent(
            event_type=EventType.LLM_RESPONSE_READY,
            call_id="call-003",
            tenant_id="beta_inc",
            worker_id="worker-01:abc",
            payload={"text": "Hello!", "actions": [{"type": "book"}]},
        )
        json_str = original.to_json()
        restored = SystemEvent.from_json(json_str)
        assert restored.event_type == original.event_type
        assert restored.call_id == original.call_id
        assert restored.worker_id == original.worker_id
        assert restored.payload == original.payload


class TestWebSocketMessages:
    """Tests for WebSocket message models."""

    def test_audio_input_message(self) -> None:
        """Test AudioInputMessage."""
        msg = AudioInputMessage(
            type="audio_input",
            timestamp=1718882456.123,
            data="base64encodeddata",
            duration_ms=200,
            sequence=42,
        )
        assert msg.duration_ms == 200
        assert msg.sequence == 42

    def test_audio_output_message(self) -> None:
        """Test AudioOutputMessage."""
        msg = AudioOutputMessage(
            type="audio_output",
            timestamp=1718882456.456,
            data="base64encodeddata",
            duration_ms=1500,
            sequence=15,
            is_interruption=False,
        )
        assert msg.is_interruption is False

    def test_transcript_message(self) -> None:
        """Test TranscriptMessage."""
        msg = TranscriptMessage(
            type="transcript",
            speaker="caller",
            text="I'd like to book an appointment",
            is_final=True,
            confidence=0.95,
        )
        assert msg.confidence == 0.95
        assert msg.speaker == "caller"

    def test_status_message(self) -> None:
        """Test StatusMessage."""
        msg = StatusMessage(
            type="status", state="processing", detail="llm_generating", estimated_ms=800
        )
        assert msg.estimated_ms == 800

    def test_control_message(self) -> None:
        """Test ControlMessage."""
        msg = ControlMessage(type="control", action="hold")
        assert msg.action == "hold"

    def test_error_message(self) -> None:
        """Test ErrorMessage."""
        msg = ErrorMessage(
            type="error",
            code="LLM_TIMEOUT",
            message="Response generation took too long",
            recoverable=True,
        )
        assert msg.recoverable is True
        assert msg.code == "LLM_TIMEOUT"
