"""
Pydantic models for the Owlbell orchestration layer.

Defines all runtime data models used across the orchestration system:
- ActiveSession: Represents an in-progress phone call
- WorkerNode: Represents an AI worker (Celery + GPU)
- QueuedCall: Represents a call waiting in the priority queue
- SystemEvent: Represents an event published to the event bus
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class CallState(str, Enum):
    """States in the call lifecycle state machine."""

    CREATED = "created"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    CONNECTING = "connecting"
    ACTIVE = "active"
    PROCESSING = "processing"
    HOLDING = "holding"
    ENDED = "ended"
    ARCHIVED = "archived"


class WorkerStatus(str, Enum):
    """Status of an AI worker node."""

    STARTING = "starting"
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class QueuePriority(int, Enum):
    """Priority levels for call queue. Lower = higher priority."""

    EMERGENCY = 1
    VIP = 10
    CALLBACK = 20
    STANDARD = 30
    LOW = 40


class EventType(str, Enum):
    """Types of system events published to the event bus."""

    # Call lifecycle
    CALL_STARTED = "call_started"
    CALL_QUEUED = "call_queued"
    CALL_ASSIGNED = "call_assigned"
    CALL_CONNECTED = "call_connected"
    CALL_ACTIVE = "call_active"
    CALL_HOLDING = "call_holding"
    CALL_ENDED = "call_ended"
    CALL_TRANSFERRED = "call_transferred"

    # Audio/Processing
    TRANSCRIPT_READY = "transcript_ready"
    AUDIO_CHUNK_RECEIVED = "audio_chunk_received"
    AUDIO_CHUNK_SENT = "audio_chunk_sent"
    LLM_RESPONSE_READY = "llm_response_ready"
    TTS_AUDIO_READY = "tts_audio_ready"

    # Worker lifecycle
    WORKER_STARTED = "worker_started"
    WORKER_HEARTBEAT = "worker_heartbeat"
    WORKER_BUSY = "worker_busy"
    WORKER_IDLE = "worker_idle"
    WORKER_DRAINING = "worker_draining"
    WORKER_UNHEALTHY = "worker_unhealthy"
    WORKER_OFFLINE = "worker_offline"
    WORKER_RESTARTED = "worker_restarted"

    # System
    SYSTEM_OVERLOAD = "system_overload"
    SYSTEM_RECOVERED = "system_recovered"
    DEGRADATION_ENABLED = "degradation_enabled"
    DEGRADATION_DISABLED = "degradation_disabled"

    # Errors
    ERROR_WORKER_CRASH = "error_worker_crash"
    ERROR_GPU_OOM = "error_gpu_oom"
    ERROR_WS_DISCONNECT = "error_ws_disconnect"
    ERROR_STT_FAILED = "error_stt_failed"
    ERROR_LLM_TIMEOUT = "error_llm_timeout"
    ERROR_TTS_FAILED = "error_tts_failed"


class ActiveSession(BaseModel):
    """Represents a single active phone call session.

    Stored in Redis as HASH at key: ``session:{call_id}``
    TTL: 24 hours (automatic cleanup of orphaned sessions)
    """

    model_config = ConfigDict(populate_by_name=True)

    call_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str  # Business identifier (multi-tenant)
    phone_number: str  # Called number (DID)
    caller_number: str  # Caller ID (E.164 format)
    caller_name: Optional[str] = None

    # State machine
    state: CallState = CallState.CREATED
    state_history: List[Dict[str, Any]] = Field(default_factory=list)

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    last_activity_at: datetime = Field(default_factory=datetime.utcnow)

    # Assignment
    worker_id: Optional[str] = None
    worker_node: Optional[str] = None
    gpu_device: Optional[int] = None
    queue_position: Optional[int] = None
    queue_entered_at: Optional[datetime] = None

    # Agent configuration (denormalized for fast access)
    agent_id: str
    agent_name: str = ""
    agent_config: Dict[str, Any] = Field(default_factory=dict)

    # Conversation
    transcript: List[Dict[str, Any]] = Field(default_factory=list)
    current_utterance: Optional[str] = None

    # Metrics
    audio_chunks_received: int = 0
    audio_chunks_sent: int = 0
    llm_calls: int = 0
    stt_calls: int = 0
    tts_calls: int = 0
    total_audio_seconds: float = 0.0

    # Quality
    mos_score: Optional[float] = None  # Mean Opinion Score
    error_count: int = 0
    last_error: Optional[str] = None

    # WebSocket
    ws_connected: bool = False
    ws_client_ip: Optional[str] = None

    def to_redis_hash(self) -> Dict[str, str]:
        """Serialize to Redis HASH (all values as strings)."""
        return {
            "call_id": self.call_id,
            "tenant_id": self.tenant_id,
            "phone_number": self.phone_number,
            "caller_number": self.caller_number,
            "caller_name": self.caller_name or "",
            "state": self.state.value,
            "state_history": json.dumps(
                [{k: str(v) for k, v in item.items()} for item in self.state_history]
            ),
            "created_at": self.created_at.isoformat(),
            "answered_at": self.answered_at.isoformat() if self.answered_at else "",
            "ended_at": self.ended_at.isoformat() if self.ended_at else "",
            "last_activity_at": self.last_activity_at.isoformat(),
            "worker_id": self.worker_id or "",
            "worker_node": self.worker_node or "",
            "gpu_device": str(self.gpu_device) if self.gpu_device is not None else "",
            "queue_position": (
                str(self.queue_position) if self.queue_position is not None else ""
            ),
            "queue_entered_at": (
                self.queue_entered_at.isoformat() if self.queue_entered_at else ""
            ),
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_config": json.dumps(self.agent_config),
            "transcript": json.dumps(self.transcript),
            "current_utterance": self.current_utterance or "",
            "audio_chunks_received": str(self.audio_chunks_received),
            "audio_chunks_sent": str(self.audio_chunks_sent),
            "llm_calls": str(self.llm_calls),
            "stt_calls": str(self.stt_calls),
            "tts_calls": str(self.tts_calls),
            "total_audio_seconds": str(self.total_audio_seconds),
            "mos_score": str(self.mos_score) if self.mos_score is not None else "",
            "error_count": str(self.error_count),
            "last_error": self.last_error or "",
            "ws_connected": "1" if self.ws_connected else "0",
            "ws_client_ip": self.ws_client_ip or "",
        }

    @classmethod
    def from_redis_hash(cls, data: Dict[str, str]) -> "ActiveSession":
        """Deserialize from Redis HASH."""
        return cls(
            call_id=data["call_id"],
            tenant_id=data["tenant_id"],
            phone_number=data["phone_number"],
            caller_number=data["caller_number"],
            caller_name=data.get("caller_name") or None,
            state=CallState(data["state"]),
            state_history=json.loads(data.get("state_history", "[]")),
            created_at=datetime.fromisoformat(data["created_at"]),
            answered_at=(
                datetime.fromisoformat(data["answered_at"])
                if data.get("answered_at")
                else None
            ),
            ended_at=(
                datetime.fromisoformat(data["ended_at"])
                if data.get("ended_at")
                else None
            ),
            last_activity_at=datetime.fromisoformat(data["last_activity_at"]),
            worker_id=data.get("worker_id") or None,
            worker_node=data.get("worker_node") or None,
            gpu_device=int(data["gpu_device"]) if data.get("gpu_device") else None,
            queue_position=(
                int(data["queue_position"]) if data.get("queue_position") else None
            ),
            queue_entered_at=(
                datetime.fromisoformat(data["queue_entered_at"])
                if data.get("queue_entered_at")
                else None
            ),
            agent_id=data["agent_id"],
            agent_name=data.get("agent_name", ""),
            agent_config=json.loads(data.get("agent_config", "{}")),
            transcript=json.loads(data.get("transcript", "[]")),
            current_utterance=data.get("current_utterance") or None,
            audio_chunks_received=int(data.get("audio_chunks_received", 0)),
            audio_chunks_sent=int(data.get("audio_chunks_sent", 0)),
            llm_calls=int(data.get("llm_calls", 0)),
            stt_calls=int(data.get("stt_calls", 0)),
            tts_calls=int(data.get("tts_calls", 0)),
            total_audio_seconds=float(data.get("total_audio_seconds", 0)),
            mos_score=float(data["mos_score"]) if data.get("mos_score") else None,
            error_count=int(data.get("error_count", 0)),
            last_error=data.get("last_error") or None,
            ws_connected=data.get("ws_connected") == "1",
            ws_client_ip=data.get("ws_client_ip") or None,
        )


class WorkerNode(BaseModel):
    """Represents a single AI worker node (Celery worker + GPU).

    Stored in Redis as HASH at key: ``worker:{worker_id}``
    TTL: 10 seconds (refreshed by heartbeat)
    """

    model_config = ConfigDict(populate_by_name=True)

    worker_id: str  # hostname:uuid format, e.g., "worker-01:a1b2c3d4"
    hostname: str  # Docker container hostname
    ip_address: str = ""
    pid: int = 0

    # Status
    status: WorkerStatus = WorkerStatus.STARTING
    status_changed_at: datetime = Field(default_factory=datetime.utcnow)

    # Capabilities
    gpu_device: int = 0
    gpu_name: str = ""
    gpu_memory_total: int = 0  # MB
    gpu_memory_free: int = 0  # MB
    supported_models: List[str] = Field(default_factory=list)

    # Current load
    current_sessions: List[str] = Field(default_factory=list)
    max_concurrent_sessions: int = 4  # Configurable per GPU
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    gpu_utilization: float = 0.0
    gpu_memory_used: int = 0  # MB

    # Performance metrics
    avg_inference_latency_ms: float = 0.0  # Rolling average
    total_requests_served: int = 0
    errors_count: int = 0
    last_error: Optional[str] = None

    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat_at: datetime = Field(default_factory=datetime.utcnow)

    # Version (for rolling deployments)
    version: str = "1.0.0"

    def to_redis_hash(self) -> Dict[str, str]:
        """Serialize to Redis HASH."""
        return {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "ip_address": self.ip_address,
            "pid": str(self.pid),
            "status": self.status.value,
            "status_changed_at": self.status_changed_at.isoformat(),
            "gpu_device": str(self.gpu_device),
            "gpu_name": self.gpu_name,
            "gpu_memory_total": str(self.gpu_memory_total),
            "gpu_memory_free": str(self.gpu_memory_free),
            "supported_models": json.dumps(self.supported_models),
            "current_sessions": json.dumps(self.current_sessions),
            "max_concurrent_sessions": str(self.max_concurrent_sessions),
            "cpu_percent": str(self.cpu_percent),
            "memory_percent": str(self.memory_percent),
            "gpu_utilization": str(self.gpu_utilization),
            "gpu_memory_used": str(self.gpu_memory_used),
            "avg_inference_latency_ms": str(self.avg_inference_latency_ms),
            "total_requests_served": str(self.total_requests_served),
            "errors_count": str(self.errors_count),
            "last_error": self.last_error or "",
            "started_at": self.started_at.isoformat(),
            "last_heartbeat_at": self.last_heartbeat_at.isoformat(),
            "version": self.version,
        }

    @classmethod
    def from_redis_hash(cls, data: Dict[str, str]) -> "WorkerNode":
        """Deserialize from Redis HASH."""
        return cls(
            worker_id=data["worker_id"],
            hostname=data["hostname"],
            ip_address=data.get("ip_address", ""),
            pid=int(data.get("pid", 0)),
            status=WorkerStatus(data.get("status", "starting")),
            status_changed_at=datetime.fromisoformat(
                data.get("status_changed_at", datetime.utcnow().isoformat())
            ),
            gpu_device=int(data.get("gpu_device", 0)),
            gpu_name=data.get("gpu_name", ""),
            gpu_memory_total=int(data.get("gpu_memory_total", 0)),
            gpu_memory_free=int(data.get("gpu_memory_free", 0)),
            supported_models=json.loads(data.get("supported_models", "[]")),
            current_sessions=json.loads(data.get("current_sessions", "[]")),
            max_concurrent_sessions=int(data.get("max_concurrent_sessions", 4)),
            cpu_percent=float(data.get("cpu_percent", 0)),
            memory_percent=float(data.get("memory_percent", 0)),
            gpu_utilization=float(data.get("gpu_utilization", 0)),
            gpu_memory_used=int(data.get("gpu_memory_used", 0)),
            avg_inference_latency_ms=float(data.get("avg_inference_latency_ms", 0)),
            total_requests_served=int(data.get("total_requests_served", 0)),
            errors_count=int(data.get("errors_count", 0)),
            last_error=data.get("last_error") or None,
            started_at=datetime.fromisoformat(
                data.get("started_at", datetime.utcnow().isoformat())
            ),
            last_heartbeat_at=datetime.fromisoformat(
                data.get("last_heartbeat_at", datetime.utcnow().isoformat())
            ),
            version=data.get("version", "1.0.0"),
        )

    @property
    def available_slots(self) -> int:
        """Number of additional sessions this worker can handle."""
        if self.status not in (WorkerStatus.IDLE, WorkerStatus.BUSY):
            return 0
        return max(0, self.max_concurrent_sessions - len(self.current_sessions))

    @property
    def is_available(self) -> bool:
        """Whether this worker can accept new sessions."""
        return self.status == WorkerStatus.IDLE or (
            self.status == WorkerStatus.BUSY and self.available_slots > 0
        )


class QueuedCall(BaseModel):
    """Represents a call waiting in the priority queue.

    Stored in Redis Sorted Set: ``queue:{tenant_id}`` (score = priority + timestamp)
    Also stored as HASH: ``queued_call:{call_id}``
    TTL: 1 hour
    """

    model_config = ConfigDict(populate_by_name=True)

    call_id: str
    tenant_id: str
    caller_number: str
    caller_name: Optional[str] = None
    priority: QueuePriority = QueuePriority.STANDARD

    # Queue metadata
    position: int = 0
    estimated_wait_seconds: int = 0
    queue_entered_at: datetime = Field(default_factory=datetime.utcnow)

    # Business hours / routing
    requested_agent_id: Optional[str] = None
    transfer_target: Optional[str] = None  # Extension or external number

    # Announcement tracking
    last_announcement_at: Optional[datetime] = None
    announcements_count: int = 0

    # Reason for queue (used for analytics)
    queue_reason: str = "no_workers_available"  # or "all_gpus_busy", "business_hours"

    def get_queue_score(self) -> float:
        """Calculate Redis sorted set score. Lower = higher priority.

        Score format: priority + (timestamp / 1e10)
        Example: 30.1704067200
        This ensures FIFO within same priority level.
        """
        timestamp_part = self.queue_entered_at.timestamp()
        return float(self.priority.value) + (timestamp_part / 1e10)


class SystemEvent(BaseModel):
    """An event published to the event bus.

    Serialized as JSON and published to Redis pub/sub channel.
    Also persisted to Redis Stream for replay (max 10,000 entries).
    """

    model_config = ConfigDict(populate_by_name=True)

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Context
    call_id: Optional[str] = None
    tenant_id: Optional[str] = None
    worker_id: Optional[str] = None

    # Payload (event-specific data)
    payload: Dict[str, Any] = Field(default_factory=dict)

    # Metadata
    source: str = "orchestrator"  # Service that emitted the event
    version: str = "1.0.0"

    def to_json(self) -> str:
        """Serialize to JSON string for pub/sub."""
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str) -> "SystemEvent":
        """Deserialize from JSON string."""
        return cls.model_validate_json(data)


# --- WebSocket Message Models ---


class AudioInputMessage(BaseModel):
    """Audio chunk from caller (client -> server)."""

    type: str = "audio_input"
    timestamp: float
    data: str  # base64 encoded PCM
    duration_ms: int
    sequence: int


class AudioOutputMessage(BaseModel):
    """Audio chunk to caller - TTS output (server -> client)."""

    type: str = "audio_output"
    timestamp: float
    data: str  # base64 encoded PCM
    duration_ms: int
    sequence: int
    is_interruption: bool = False


class TranscriptMessage(BaseModel):
    """Transcript update (server -> client)."""

    type: str = "transcript"
    speaker: str  # "caller" or "agent"
    text: str
    is_final: bool = True
    confidence: Optional[float] = None


class StatusMessage(BaseModel):
    """Status/progress update (server -> client)."""

    type: str = "status"
    state: str
    detail: str = ""
    estimated_ms: int = 0


class ControlMessage(BaseModel):
    """Control message (bidirectional)."""

    type: str = "control"
    action: str  # mute, unmute, hold, resume, end_call
    reason: Optional[str] = None
    duration_seconds: Optional[int] = None


class ErrorMessage(BaseModel):
    """Error message (server -> client)."""

    type: str = "error"
    code: str
    message: str
    recoverable: bool = True


class WebSocketMessage(BaseModel):
    """Union type for all WebSocket messages."""

    type: str
    payload: Optional[Dict[str, Any]] = None
