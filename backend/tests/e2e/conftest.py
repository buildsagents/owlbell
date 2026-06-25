"""
Shared fixtures for end-to-end integration tests.

Provides comprehensive test infrastructure:
- Test database (SQLite in-memory)
- Test Redis (fakeredis)
- FastAPI test client (httpx.AsyncClient)
- Mock external services (FreeSWITCH, AI pipeline)
- Tenant and user fixtures
- Event loop management

Location: backend/tests/e2e/conftest.py
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import uuid
from collections.abc import AsyncGenerator
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

# Ensure project root is importable
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.api.main import create_app, API_PREFIX
from backend.orchestrator.session_manager import SessionManager
from backend.orchestrator.event_bus import EventBus
from backend.orchestrator.models import (
    ActiveSession,
    CallState,
    EventType,
    QueuePriority,
    QueuedCall,
    SystemEvent,
    WorkerNode,
    WorkerStatus,
)
from backend.orchestrator.circuit_breaker import CircuitBreaker, get_circuit_breaker, reset_all_circuits


# ---------------------------------------------------------------------------
# pytest-asyncio configuration
# ---------------------------------------------------------------------------

pytest_plugins = ["pytest_asyncio"]


# ---------------------------------------------------------------------------
# FakeRedis fixture
# ---------------------------------------------------------------------------


class FakeRedisClient:
    """Enhanced fake Redis that implements enough of the async Redis API."""

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._sets: Dict[str, set] = {}
        self._lists: Dict[str, list] = {}
        self._streams: Dict[str, list] = {}
        self._pubsub_channels: Dict[str, list] = {}
        self._counters: Dict[str, int] = {}
        self._expiry: Dict[str, float] = {}

    # ---- String operations ----

    async def set(self, key: str, value: Any, **kwargs) -> None:
        self._data[key] = str(value) if not isinstance(value, str) else value

    async def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    async def delete(self, key: str) -> int:
        count = 0
        for k in [key] if isinstance(key, str) else key:
            if k in self._data:
                del self._data[k]
                count += 1
            self._sets.pop(k, None)
            self._lists.pop(k, None)
            self._streams.pop(k, None)
        return count

    async def exists(self, key: str) -> int:
        return 1 if key in self._data or key in self._sets else 0

    async def expire(self, key: str, seconds: int) -> None:
        self._expiry[key] = seconds

    # ---- Hash operations ----

    async def hset(self, key: str, field: str = None, value: str = None, mapping: dict = None) -> None:
        if key not in self._data:
            self._data[key] = {}
        if mapping:
            self._data[key].update(mapping)
        elif field is not None:
            self._data[key][field] = value

    async def hget(self, key: str, field: str) -> Optional[str]:
        if key not in self._data or not isinstance(self._data[key], dict):
            return None
        return self._data[key].get(field)

    async def hgetall(self, key: str) -> dict:
        if key not in self._data or not isinstance(self._data[key], dict):
            return {}
        return dict(self._data[key])

    async def hincrby(self, key: str, field: str, increment: int = 1) -> int:
        if key not in self._data or not isinstance(self._data[key], dict):
            self._data[key] = {}
        current = int(self._data[key].get(field, 0))
        self._data[key][field] = str(current + increment)
        return current + increment

    # ---- Set operations ----

    async def sadd(self, key: str, member: str) -> None:
        if key not in self._sets:
            self._sets[key] = set()
        self._sets[key].add(member)

    async def srem(self, key: str, member: str) -> None:
        if key in self._sets and member in self._sets[key]:
            self._sets[key].discard(member)

    async def smembers(self, key: str) -> set:
        return self._sets.get(key, set()).copy()

    async def scard(self, key: str) -> int:
        return len(self._sets.get(key, set()))

    async def sinter(self, *keys: str) -> set:
        sets = [self._sets.get(k, set()) for k in keys]
        if not sets:
            return set()
        result = sets[0].copy()
        for s in sets[1:]:
            result &= s
        return result

    # ---- List operations ----

    async def lpush(self, key: str, value: str) -> None:
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].insert(0, value)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        if key in self._lists:
            self._lists[key] = self._lists[key][start:end + 1]

    async def lrange(self, key: str, start: int, end: int) -> list:
        return self._lists.get(key, [])[start:end + 1] if end >= 0 else []

    # ---- Stream operations ----

    async def xadd(self, key: str, fields: dict, maxlen: int = None, approximate: bool = None) -> str:
        if key not in self._streams:
            self._streams[key] = []
        entry_id = str(len(self._streams[key]) + 1)
        self._streams[key].append((entry_id, fields))
        if maxlen and len(self._streams[key]) > maxlen:
            self._streams[key] = self._streams[key][-maxlen:]
        return entry_id

    async def xrevrange(self, key: str, count: int = None) -> list:
        entries = self._streams.get(key, [])
        result = list(reversed(entries))
        return result[:count] if count else result

    async def xrange(self, key: str, min: str = "-", count: int = None) -> list:
        entries = self._streams.get(key, [])
        return entries[:count] if count else entries

    async def xdel(self, key: str, entry_id: str) -> None:
        if key in self._streams:
            self._streams[key] = [e for e in self._streams[key] if e[0] != entry_id]

    # ---- Pub/Sub ----

    async def publish(self, channel: str, message: str) -> None:
        if channel not in self._pubsub_channels:
            self._pubsub_channels[channel] = []
        self._pubsub_channels[channel].append(message)

    # ---- Pipeline ----

    def pipeline(self) -> "FakePipeline":
        return FakePipeline(self)

    # ---- Scan ----

    async def keys(self, pattern: str) -> list:
        import fnmatch
        result = []
        for k in list(self._data.keys()) + list(self._sets.keys()):
            if fnmatch.fnmatch(k, pattern):
                result.append(k)
        return list(set(result))

    # ---- Pub/Sub listener ----

    def pubsub(self) -> "FakePubSub":
        return FakePubSub(self)

    async def subscribe(self, channel: str) -> None:
        if channel not in self._pubsub_channels:
            self._pubsub_channels[channel] = []

    async def unsubscribe(self, channel: str) -> None:
        self._pubsub_channels.pop(channel, None)

    def clear_all(self) -> None:
        """Clear all data (between tests)."""
        self._data.clear()
        self._sets.clear()
        self._lists.clear()
        self._streams.clear()
        self._pubsub_channels.clear()
        self._counters.clear()
        self._expiry.clear()


class FakePipeline:
    """Fake Redis pipeline for atomic operations."""

    def __init__(self, client: FakeRedisClient) -> None:
        self._client = client
        self._ops: list = []

    def hset(self, key: str, field: str = None, value: str = None, mapping: dict = None) -> "FakePipeline":
        self._ops.append(("hset", key, field, value, mapping))
        return self

    def sadd(self, key: str, member: str) -> "FakePipeline":
        self._ops.append(("sadd", key, member))
        return self

    def srem(self, key: str, member: str) -> "FakePipeline":
        self._ops.append(("srem", key, member))
        return self

    def incr(self, key: str) -> "FakePipeline":
        self._ops.append(("incr", key))
        return self

    def decr(self, key: str) -> "FakePipeline":
        self._ops.append(("decr", key))
        return self

    def delete(self, key: str) -> "FakePipeline":
        self._ops.append(("delete", key))
        return self

    def publish(self, channel: str, message: str) -> "FakePipeline":
        self._ops.append(("publish", channel, message))
        return self

    def xadd(self, key: str, fields: dict, **kwargs) -> "FakePipeline":
        self._ops.append(("xadd", key, fields))
        return self

    def lpush(self, key: str, value: str) -> "FakePipeline":
        self._ops.append(("lpush", key, value))
        return self

    def ltrim(self, key: str, start: int, end: int) -> "FakePipeline":
        self._ops.append(("ltrim", key, start, end))
        return self

    def expire(self, key: str, seconds: int) -> "FakePipeline":
        self._ops.append(("expire", key, seconds))
        return self

    async def execute(self) -> list:
        results = []
        for op in self._ops:
            cmd = op[0]
            try:
                if cmd == "hset":
                    _, key, field, value, mapping = op
                    await self._client.hset(key, field, value, mapping=mapping)
                elif cmd == "sadd":
                    _, key, member = op
                    await self._client.sadd(key, member)
                elif cmd == "srem":
                    _, key, member = op
                    await self._client.srem(key, member)
                elif cmd == "incr":
                    _, key = op
                    self._client._counters[key] = self._client._counters.get(key, 0) + 1
                elif cmd == "decr":
                    _, key = op
                    self._client._counters[key] = self._client._counters.get(key, 0) - 1
                elif cmd == "delete":
                    _, key = op
                    await self._client.delete(key)
                elif cmd == "publish":
                    _, channel, message = op
                    await self._client.publish(channel, message)
                elif cmd == "xadd":
                    _, key, fields = op
                    await self._client.xadd(key, fields)
                elif cmd == "lpush":
                    _, key, value = op
                    await self._client.lpush(key, value)
                elif cmd == "ltrim":
                    _, key, start, end = op
                    await self._client.ltrim(key, start, end)
                elif cmd == "expire":
                    _, key, seconds = op
                    await self._client.expire(key, seconds)
                results.append(True)
            except Exception:
                results.append(False)
        self._ops.clear()
        return results


class FakePubSub:
    """Fake pub/sub for listening."""

    def __init__(self, client: FakeRedisClient) -> None:
        self._client = client
        self._subscribed: set = set()

    async def subscribe(self, channel: str) -> None:
        self._subscribed.add(channel)
        if channel not in self._client._pubsub_channels:
            self._client._pubsub_channels[channel] = []

    async def listen(self):
        """Simulated listen - yields messages that have been published."""
        import asyncio
        for channel in self._subscribed:
            messages = self._client._pubsub_channels.get(channel, [])
            for msg in messages:
                yield {"type": "message", "channel": channel, "data": msg}
            # Clear consumed messages
            self._client._pubsub_channels[channel] = []
        # Keep the generator alive
        while True:
            await asyncio.sleep(60)


# ---------------------------------------------------------------------------
# Session manager with FakeRedis
# ---------------------------------------------------------------------------


class TestSessionManager(SessionManager):
    """Session manager using FakeRedis for tests."""

    def __init__(self, redis_client: FakeRedisClient) -> None:
        self._redis = redis_client
        self.event_bus = None
        self.redis_url = "fake://localhost"

    def _get_client(self) -> FakeRedisClient:
        return self._redis


# ---------------------------------------------------------------------------
# Event bus with FakeRedis
# ---------------------------------------------------------------------------


class TestEventBus(EventBus):
    """Event bus using FakeRedis for tests."""

    def __init__(self, redis_client: FakeRedisClient) -> None:
        self._redis = redis_client
        self._subscribers = set()
        self._listener_task = None
        self._running = False
        self._event_handlers = {}
        self.redis_url = "fake://localhost"

    def _get_client(self) -> FakeRedisClient:
        return self._redis

    async def _ensure_client(self) -> FakeRedisClient:
        return self._redis


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def fake_redis() -> FakeRedisClient:
    """Create a fresh FakeRedis client for each test."""
    client = FakeRedisClient()
    yield client
    client.clear_all()


@pytest.fixture(scope="function")
def event_bus(fake_redis: FakeRedisClient) -> TestEventBus:
    """Create a test event bus with FakeRedis."""
    return TestEventBus(fake_redis)


@pytest.fixture(scope="function")
def session_manager(fake_redis: FakeRedisClient) -> TestSessionManager:
    """Create a test session manager with FakeRedis."""
    return TestSessionManager(fake_redis)


# ---------------------------------------------------------------------------
# Mock external services
# ---------------------------------------------------------------------------


class MockFreeSWITCH:
    """Mock FreeSWITCH ESL handler for testing."""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []
        self.connected: bool = True
        self.calls: Dict[str, Dict[str, Any]] = {}
        self.command_log: List[Dict[str, Any]] = []

    async def send_command(self, command: str, **kwargs) -> Dict[str, Any]:
        """Log and simulate a FreeSWITCH command."""
        entry = {"command": command, "params": kwargs, "timestamp": datetime.utcnow().isoformat()}
        self.command_log.append(entry)
        return {"status": "ok", "response": f"+OK {command}"}

    def fire_event(self, event_type: str, call_id: str, data: dict = None) -> Dict[str, Any]:
        """Simulate a FreeSWITCH event."""
        event = {
            "type": event_type,
            "call_id": call_id,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data or {},
        }
        self.events.append(event)
        return event

    def simulate_inbound_call(self, caller_number: str = "+15551234567", called_number: str = "+15559876543") -> str:
        """Simulate a complete inbound call arriving."""
        call_id = str(uuid.uuid4())
        self.calls[call_id] = {
            "call_id": call_id,
            "caller_number": caller_number,
            "called_number": called_number,
            "state": "ringing",
            "direction": "inbound",
            "created_at": datetime.utcnow().isoformat(),
        }
        self.fire_event("CHANNEL_CREATE", call_id, {
            "Caller-ANI": caller_number,
            "Destination-Number": called_number,
            "Call-Direction": "inbound",
        })
        self.fire_event("CHANNEL_CALLSTATE", call_id, {"Channel-Call-State": "ringing"})
        return call_id

    def simulate_answer(self, call_id: str) -> None:
        """Simulate call being answered."""
        if call_id in self.calls:
            self.calls[call_id]["state"] = "active"
        self.fire_event("CHANNEL_CALLSTATE", call_id, {"Channel-Call-State": "active"})
        self.fire_event("CHANNEL_ANSWER", call_id, {"Answer-State": "answered"})

    def simulate_hangup(self, call_id: str, reason: str = "hangup_by_caller") -> None:
        """Simulate call hangup."""
        if call_id in self.calls:
            self.calls[call_id]["state"] = "hangup"
        self.fire_event("CHANNEL_HANGUP", call_id, {"Hangup-Cause": "NORMAL_CLEARING"})
        self.fire_event("CHANNEL_DESTROY", call_id, {})


class MockAIPipeline:
    """Mock AI Pipeline (STT -> LLM -> TTS) for testing."""

    def __init__(self) -> None:
        self.stt_calls: List[Dict[str, Any]] = []
        self.llm_calls: List[Dict[str, Any]] = []
        self.tts_calls: List[Dict[str, Any]] = []
        self.available: bool = True
        self.failure_mode: Optional[str] = None  # "stt", "llm", "tts", "all"

    async def transcribe(self, audio_data: bytes, language: str = "en") -> Dict[str, Any]:
        """Mock STT transcription."""
        self.stt_calls.append({"audio_size": len(audio_data), "language": language})
        if self.failure_mode in ("stt", "all"):
            raise RuntimeError("STT service unavailable")
        # Simulate transcribed text based on audio size heuristic
        if len(audio_data) > 1000:
            return {"text": "Hello, I'd like to leave a message for Dr. Smith.", "confidence": 0.95, "language": language}
        elif len(audio_data) > 500:
            return {"text": "Yes, my number is 555-1234.", "confidence": 0.92, "language": language}
        return {"text": "Thank you, goodbye.", "confidence": 0.98, "language": language}

    async def generate_response(self, prompt: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        """Mock LLM response generation."""
        self.llm_calls.append({"prompt": prompt[:200], "system_prompt": system_prompt[:100] if system_prompt else None})
        if self.failure_mode in ("llm", "all"):
            raise RuntimeError("LLM service unavailable")
        # Simulate contextual response
        lower = prompt.lower()
        if "appointment" in lower or "schedule" in lower:
            return {"text": "I'd be happy to help you schedule an appointment. What day works best for you?", "tokens_used": 45}
        elif "message" in lower or "voicemail" in lower:
            return {"text": "Of course, I can take a message. Please go ahead.", "tokens_used": 30}
        elif "hours" in lower:
            return {"text": "We're open Monday through Friday, 9 AM to 5 PM. Saturday hours are 10 AM to 2 PM.", "tokens_used": 38}
        elif "goodbye" in lower or "bye" in lower:
            return {"text": "Thank you for calling. Have a wonderful day!", "tokens_used": 25}
        return {"text": "Thank you for calling. How may I assist you today?", "tokens_used": 28}

    async def synthesize(self, text: str, voice_id: str = "default") -> bytes:
        """Mock TTS synthesis."""
        self.tts_calls.append({"text": text[:200], "voice_id": voice_id})
        if self.failure_mode in ("tts", "all"):
            raise RuntimeError("TTS service unavailable")
        # Return a small audio chunk placeholder (size proportional to text length)
        return b"\x00\x01" * max(50, len(text) * 2)

    def set_failure_mode(self, mode: Optional[str]) -> None:
        """Set which AI service should fail."""
        self.failure_mode = mode

    def reset(self) -> None:
        """Reset all call logs and state."""
        self.stt_calls.clear()
        self.llm_calls.clear()
        self.tts_calls.clear()
        self.available = True
        self.failure_mode = None


# ---------------------------------------------------------------------------
# Test data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_freeswitch() -> MockFreeSWITCH:
    """Create a mock FreeSWITCH handler."""
    return MockFreeSWITCH()


@pytest.fixture
def mock_ai_pipeline() -> MockAIPipeline:
    """Create a mock AI pipeline."""
    return MockAIPipeline()


@pytest.fixture
def test_tenant_id() -> str:
    """Return a consistent test tenant ID."""
    return "test-tenant-acme-001"


@pytest.fixture
def test_tenant_id_2() -> str:
    """Return a second consistent test tenant ID."""
    return "test-tenant-beta-002"


@pytest.fixture
def sample_tenant_config() -> Dict[str, Any]:
    """Return a sample tenant configuration."""
    return {
        "id": "test-tenant-acme-001",
        "name": "Acme Dental",
        "slug": "acme-dental",
        "timezone": "America/New_York",
        "business_hours": {
            "monday": {"open": "09:00", "close": "17:00", "is_open": True},
            "tuesday": {"open": "09:00", "close": "17:00", "is_open": True},
            "wednesday": {"open": "09:00", "close": "17:00", "is_open": True},
            "thursday": {"open": "09:00", "close": "17:00", "is_open": True},
            "friday": {"open": "09:00", "close": "17:00", "is_open": True},
            "saturday": {"open": "10:00", "close": "14:00", "is_open": True},
            "sunday": {"is_open": False},
        },
        "ai_config": {
            "model": "llama3_8b",
            "temperature": 0.7,
            "voice": "en_US-lessac-medium",
            "greeting": "Thank you for calling Acme Dental. I'm your AI assistant. How can I help?",
            "system_prompt": "You are a professional dental receptionist assistant.",
        },
        "routing_rules": [
            {"condition": "outside_business_hours", "action": "ai_answer", "priority": 10},
            {"condition": "keyword_emergency", "action": "transfer_immediately", "priority": 100},
            {"condition": "vip_caller", "action": "priority_queue", "priority": 50},
        ],
        "max_call_duration": 600,
        "concurrent_calls_max": 5,
    }


@pytest.fixture
def sample_test_users() -> List[Dict[str, Any]]:
    """Return sample test users."""
    return [
        {"email": "admin@acme.com", "password": "SecurePass123!", "role": "admin"},
        {"email": "manager@acme.com", "password": "SecurePass123!", "role": "manager"},
        {"email": "agent@acme.com", "password": "SecurePass123!", "role": "agent"},
    ]


@pytest.fixture
def sample_caller_info() -> Dict[str, str]:
    """Return sample caller information."""
    return {
        "name": "John Smith",
        "phone": "+15551234567",
        "email": "john.smith@email.com",
    }


# ---------------------------------------------------------------------------
# Webhook test helpers
# ---------------------------------------------------------------------------


def generate_webhook_signature(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature."""
    expected = generate_webhook_signature(payload, secret)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------


async def wait_for_condition(
    condition_fn,
    timeout_seconds: float = 5.0,
    check_interval: float = 0.1,
) -> bool:
    """Wait for an async condition to become True."""
    import asyncio
    elapsed = 0.0
    while elapsed < timeout_seconds:
        if await condition_fn() if asyncio.iscoroutinefunction(condition_fn) else condition_fn():
            return True
        await asyncio.sleep(check_interval)
        elapsed += check_interval
    return False


# ---------------------------------------------------------------------------
# Event bus assertion helpers
# ---------------------------------------------------------------------------


class EventCapture:
    """Capture events from the event bus for assertions."""

    def __init__(self, event_bus: TestEventBus) -> None:
        self.event_bus = event_bus
        self.events: List[SystemEvent] = []
        self._handler = None

    def start(self) -> None:
        """Start capturing events."""
        for et in EventType:
            self.event_bus.on(et, self._on_event)

    def stop(self) -> None:
        """Stop capturing events."""
        for et in EventType:
            self.event_bus.off(et, self._on_event)

    def _on_event(self, event: SystemEvent) -> None:
        self.events.append(event)

    def get_events_by_type(self, event_type: EventType) -> List[SystemEvent]:
        """Get all captured events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def get_events_by_call(self, call_id: str) -> List[SystemEvent]:
        """Get all captured events for a specific call."""
        return [e for e in self.events if e.call_id == call_id]

    def get_events_by_tenant(self, tenant_id: str) -> List[SystemEvent]:
        """Get all captured events for a specific tenant."""
        return [e for e in self.events if e.tenant_id == tenant_id]

    def has_event_type(self, event_type: EventType) -> bool:
        """Check if any event of the given type was captured."""
        return any(e.event_type == event_type for e in self.events)

    def assert_event_sequence(self, expected_types: List[EventType]) -> None:
        """Assert that events occurred in the expected order."""
        actual_types = [e.event_type for e in self.events]
        assert actual_types == expected_types, f"Expected {expected_types}, got {actual_types}"


@pytest.fixture
def event_capture(event_bus: TestEventBus) -> EventCapture:
    """Create an event capture helper."""
    capture = EventCapture(event_bus)
    capture.start()
    yield capture
    capture.stop()


# ---------------------------------------------------------------------------
# Test session lifecycle helper
# ---------------------------------------------------------------------------


class CallSimulator:
    """Simulate a complete call lifecycle for end-to-end testing."""

    def __init__(
        self,
        freeswitch: MockFreeSWITCH,
        ai_pipeline: MockAIPipeline,
        session_manager: TestSessionManager,
        event_bus: TestEventBus,
    ) -> None:
        self.fs = freeswitch
        self.ai = ai_pipeline
        self.sessions = session_manager
        self.bus = event_bus

    async def simulate_inbound_call(
        self,
        tenant_id: str,
        caller_number: str = "+15551234567",
        called_number: str = "+15559876543",
    ) -> ActiveSession:
        """Simulate a complete inbound call flow."""
        # Step 1: FreeSWITCH receives the call
        call_id = self.fs.simulate_inbound_call(caller_number, called_number)

        # Step 2: Create session in session manager
        session = ActiveSession(
            call_id=call_id,
            tenant_id=tenant_id,
            phone_number=called_number,
            caller_number=caller_number,
            caller_name="Test Caller",
            agent_id=f"agent-{tenant_id}",
            agent_name="AI Receptionist",
            state=CallState.CREATED,
        )
        await self.sessions.create_session(session)

        # Step 3: Transition to QUEUED
        await self.sessions.transition_state(call_id, CallState.QUEUED, reason="new_call")

        # Step 4: Assign to worker
        await self.sessions.transition_state(call_id, CallState.ASSIGNED, reason="worker_available")

        # Step 5: Connect
        await self.sessions.transition_state(call_id, CallState.CONNECTING, reason="worker_connecting")

        # Step 6: Answer
        self.fs.simulate_answer(call_id)
        answered = await self.sessions.transition_state(call_id, CallState.ACTIVE, reason="call_answered")

        return answered

    async def simulate_conversation_turn(
        self,
        session: ActiveSession,
        caller_audio: bytes = None,
        expected_intent: str = "message",
    ) -> Dict[str, Any]:
        """Simulate one turn of conversation (caller speaks -> AI responds)."""
        call_id = session.call_id

        # Transition to PROCESSING
        await self.sessions.transition_state(call_id, CallState.PROCESSING, reason="audio_received")

        # STT: Transcribe caller audio
        audio = caller_audio or b"\x00\x01" * 2000
        transcript = await self.ai.transcribe(audio)

        # Update session with transcript
        session.transcript.append({"speaker": "caller", "text": transcript["text"], "timestamp": datetime.utcnow().isoformat()})
        await self.sessions.update_session(call_id, {"transcript": session.transcript})

        # LLM: Generate response
        prompt = f"Caller said: {transcript['text']}\nRespond as a helpful receptionist."
        response = await self.ai.generate_response(prompt, system_prompt="You are a professional receptionist.")

        # TTS: Synthesize response
        audio_response = await self.ai.synthesize(response["text"])

        # Update transcript with AI response
        session.transcript.append({"speaker": "ai", "text": response["text"], "timestamp": datetime.utcnow().isoformat()})
        await self.sessions.update_session(call_id, {
            "transcript": session.transcript,
            "last_activity_at": datetime.utcnow(),
        })

        # Transition back to ACTIVE
        await self.sessions.transition_state(call_id, CallState.ACTIVE, reason="response_sent")

        return {
            "transcript": transcript,
            "response": response,
            "audio_response_size": len(audio_response),
            "session": await self.sessions.get_session(call_id),
        }

    async def end_call(self, call_id: str, reason: str = "hangup_by_caller") -> Optional[ActiveSession]:
        """End a simulated call."""
        self.fs.simulate_hangup(call_id, reason)
        return await self.sessions.end_session(call_id, reason=reason)

    async def simulate_message_taking(
        self,
        session: ActiveSession,
        caller_message: str = "Please tell Dr. Smith I'll be 10 minutes late for my appointment.",
    ) -> Dict[str, Any]:
        """Simulate a message-taking conversation flow."""
        results = []

        # Turn 1: Caller says they want to leave a message
        turn1 = await self.simulate_conversation_turn(
            session,
            caller_audio=b"\x00\x01" * 2500,  # Simulated audio saying "I'd like to leave a message"
        )
        results.append(turn1)

        # Turn 2: Caller leaves the actual message
        turn2 = await self.simulate_conversation_turn(
            session,
            caller_audio=b"\x00\x01" * 3000,  # Simulated audio with the message
        )
        results.append(turn2)

        # Turn 3: Confirm and goodbye
        turn3 = await self.simulate_conversation_turn(
            session,
            caller_audio=b"\x00\x01" * 500,  # "Thank you, goodbye"
        )
        results.append(turn3)

        # End the call
        ended = await self.end_call(session.call_id, "hangup_by_caller")

        return {
            "conversation_turns": results,
            "message": caller_message,
            "ended_session": ended,
        }

    async def simulate_appointment_booking(
        self,
        session: ActiveSession,
        preferred_date: date = None,
        preferred_time: time = None,
    ) -> Dict[str, Any]:
        """Simulate an appointment booking conversation."""
        results = []

        # Turn 1: Caller requests appointment
        turn1 = await self.simulate_conversation_turn(
            session,
            caller_audio=b"\x00\x01" * 2200,
        )
        results.append(turn1)

        # Turn 2: Caller specifies date
        turn2 = await self.simulate_conversation_turn(
            session,
            caller_audio=b"\x00\x01" * 1800,
        )
        results.append(turn2)

        # Turn 3: Caller confirms
        turn3 = await self.simulate_conversation_turn(
            session,
            caller_audio=b"\x00\x01" * 1200,
        )
        results.append(turn3)

        # End the call
        ended = await self.end_call(session.call_id, "hangup_by_caller")

        return {
            "conversation_turns": results,
            "appointment_date": preferred_date or date.today() + timedelta(days=1),
            "ended_session": ended,
        }


@pytest.fixture
def call_simulator(
    mock_freeswitch: MockFreeSWITCH,
    mock_ai_pipeline: MockAIPipeline,
    session_manager: TestSessionManager,
    event_bus: TestEventBus,
) -> CallSimulator:
    """Create a call simulator for e2e testing."""
    return CallSimulator(mock_freeswitch, mock_ai_pipeline, session_manager, event_bus)
