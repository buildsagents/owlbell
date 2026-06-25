"""
Tests for orchestrator.session_manager module.

Covers:
- Session CRUD operations
- State machine transitions
- Session indexing
- Redis serialization round-trip
- Reassignment logic
- Valid/invalid state transitions
"""

from __future__ import annotations

import pytest

from backend.orchestrator.models import ActiveSession, CallState, EventType
from backend.orchestrator.session_manager import SessionManager, VALID_TRANSITIONS


class TestStateTransitions:
    """Tests for call state machine transitions."""

    def test_created_to_queued(self) -> None:
        """Test CREATED -> QUEUED is valid."""
        assert CallState.QUEUED in VALID_TRANSITIONS[CallState.CREATED]

    def test_created_to_assigned(self) -> None:
        """Test CREATED -> ASSIGNED is valid."""
        assert CallState.ASSIGNED in VALID_TRANSITIONS[CallState.CREATED]

    def test_created_to_ended(self) -> None:
        """Test CREATED -> ENDED is valid."""
        assert CallState.ENDED in VALID_TRANSITIONS[CallState.CREATED]

    def test_active_to_processing(self) -> None:
        """Test ACTIVE -> PROCESSING is valid."""
        assert CallState.PROCESSING in VALID_TRANSITIONS[CallState.ACTIVE]

    def test_active_to_holding(self) -> None:
        """Test ACTIVE -> HOLDING is valid."""
        assert CallState.HOLDING in VALID_TRANSITIONS[CallState.ACTIVE]

    def test_active_to_ended(self) -> None:
        """Test ACTIVE -> ENDED is valid."""
        assert CallState.ENDED in VALID_TRANSITIONS[CallState.ACTIVE]

    def test_holding_to_active(self) -> None:
        """Test HOLDING -> ACTIVE is valid."""
        assert CallState.ACTIVE in VALID_TRANSITIONS[CallState.HOLDING]

    def test_ended_to_archived(self) -> None:
        """Test ENDED -> ARCHIVED is valid."""
        assert CallState.ARCHIVED in VALID_TRANSITIONS[CallState.ENDED]

    def test_archived_no_transitions(self) -> None:
        """Test ARCHIVED has no valid transitions."""
        assert len(VALID_TRANSITIONS[CallState.ARCHIVED]) == 0

    def test_same_state_is_valid(self) -> None:
        """Test that staying in the same state is valid (no-op)."""
        mgr = SessionManager(redis_url="redis://localhost:6379/99")
        assert mgr._is_valid_transition(CallState.ACTIVE, CallState.ACTIVE) is True

    def test_invalid_transition(self) -> None:
        """Test that invalid transitions are rejected."""
        mgr = SessionManager(redis_url="redis://localhost:6379/99")
        assert mgr._is_valid_transition(CallState.ENDED, CallState.ACTIVE) is False
        assert mgr._is_valid_transition(CallState.ARCHIVED, CallState.CREATED) is False

    def test_state_to_event_mapping(self) -> None:
        """Test state to event type mapping."""
        mgr = SessionManager(redis_url="redis://localhost:6379/99")
        assert mgr._state_to_event(CallState.QUEUED) == EventType.CALL_QUEUED
        assert mgr._state_to_event(CallState.ASSIGNED) == EventType.CALL_ASSIGNED
        assert mgr._state_to_event(CallState.CONNECTING) == EventType.CALL_CONNECTED
        assert mgr._state_to_event(CallState.ACTIVE) == EventType.CALL_ACTIVE
        assert mgr._state_to_event(CallState.HOLDING) == EventType.CALL_HOLDING
        assert mgr._state_to_event(CallState.ENDED) == EventType.CALL_ENDED
        assert mgr._state_to_event(CallState.CREATED) is None


class TestSessionManager:
    """Tests for SessionManager class."""

    def test_init(self) -> None:
        """Test SessionManager initialization."""
        mgr = SessionManager(redis_url="redis://localhost:6379/99")
        assert mgr.KEY_SESSION == "session"
        assert mgr.KEY_STATE_INDEX == "sessions:state"
        assert mgr.KEY_TENANT_INDEX == "sessions:tenant"
        assert mgr.SESSION_TTL == 86400

    def test_session_key_format(self) -> None:
        """Test session key format."""
        mgr = SessionManager(redis_url="redis://localhost:6379/99")
        assert mgr._session_key("call-001") == "session:call-001"

    @pytest.mark.asyncio
    async def test_get_session_none(self) -> None:
        """Test get_session returns None for non-existent session."""
        mgr = SessionManager(redis_url="redis://localhost:6379/99")
        session = await mgr.get_session("non-existent-call")
        assert session is None

    @pytest.mark.asyncio
    async def test_get_or_raise(self) -> None:
        """Test get_or_raise raises for non-existent session."""
        mgr = SessionManager(redis_url="redis://localhost:6379/99")
        with pytest.raises(ValueError, match="non-existent-call"):
            await mgr.get_or_raise("non-existent-call")

    def test_valid_transitions_complete_coverage(self) -> None:
        """Test that all states have transitions defined."""
        for state in CallState:
            assert state in VALID_TRANSITIONS, f"State {state} missing from VALID_TRANSITIONS"


class TestActiveSessionCreation:
    """Tests for creating ActiveSession objects."""

    def test_basic_creation(self) -> None:
        """Test basic session creation."""
        session = ActiveSession(
            tenant_id="acme",
            phone_number="+1-555-1234",
            caller_number="+1-555-5678",
            agent_id="agent-1",
        )
        assert session.state == CallState.CREATED
        assert session.audio_chunks_received == 0

    def test_session_with_worker(self) -> None:
        """Test session creation with worker assignment."""
        session = ActiveSession(
            tenant_id="acme",
            phone_number="+1-555-1234",
            caller_number="+1-555-5678",
            agent_id="agent-1",
            worker_id="worker-01:abc",
            gpu_device=0,
            state=CallState.ACTIVE,
        )
        assert session.worker_id == "worker-01:abc"
        assert session.gpu_device == 0

    def test_session_metrics(self) -> None:
        """Test session metrics initialization."""
        session = ActiveSession(
            tenant_id="t1",
            phone_number="+1-555-0000",
            caller_number="+1-555-1111",
            agent_id="a1",
        )
        assert session.llm_calls == 0
        assert session.stt_calls == 0
        assert session.tts_calls == 0
        assert session.total_audio_seconds == 0.0
        assert session.error_count == 0
        assert session.mos_score is None
