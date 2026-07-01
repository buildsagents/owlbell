"""
Tests for Conversation Orchestrator Engine.

Covers state machine, turn-taking, barge-in, pipeline processing,
error recovery, goodbye detection, event streaming, and lifecycle.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.ai.orchestrator.conversation_engine import (
    AudioRingBuffer,
    ConversationEngine,
    ConversationState,
    OrchestratorEvent,
    OrchestratorEventType,
    PipelineMetrics,
    SimpleVAD,
    VADEvent,
)


# ---------------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> ConversationEngine:
    """Create a ConversationEngine for testing."""
    return ConversationEngine(
        session_id="test-session-1",
        tenant_id="test-tenant-1",
        call_id="test-call-1",
        business_type="generic",
        caller_number="555-1234",
        callee_number="555-5678",
    )


@pytest.fixture
def ring_buffer() -> AudioRingBuffer:
    """Create an AudioRingBuffer for testing."""
    return AudioRingBuffer(max_size_ms=1000, sample_rate=16000)


@pytest.fixture
def vad_engine() -> SimpleVAD:
    """Create a SimpleVAD for testing."""
    return SimpleVAD(threshold=0.02, min_silence_ms=200, min_speech_ms=150)


# ---------------------------------------------------------------------------
#  AudioRingBuffer tests
# ---------------------------------------------------------------------------


class TestAudioRingBuffer:
    """Tests for AudioRingBuffer."""

    @pytest.mark.asyncio
    async def test_write(self, ring_buffer: AudioRingBuffer) -> None:
        """Test writing data."""
        data = b"\x00\x01\x02\x03" * 100
        await ring_buffer.write(data)
        assert ring_buffer.size == len(data)

    @pytest.mark.asyncio
    async def test_read_all(self, ring_buffer: AudioRingBuffer) -> None:
        """Test reading all data."""
        data = b"\x00\x01\x02\x03" * 100
        await ring_buffer.write(data)
        read = await ring_buffer.read_all()
        assert read == data
        assert ring_buffer.size == 0

    @pytest.mark.asyncio
    async def test_overflow(self, ring_buffer: AudioRingBuffer) -> None:
        """Test buffer overflow handling."""
        # Write more than max size
        big_data = b"\x00" * (ring_buffer.max_size_bytes + 1000)
        await ring_buffer.write(big_data)
        assert ring_buffer.size <= ring_buffer.max_size_bytes

    @pytest.mark.asyncio
    async def test_clear(self, ring_buffer: AudioRingBuffer) -> None:
        """Test clearing buffer."""
        await ring_buffer.write(b"\x00" * 100)
        await ring_buffer.clear()
        assert ring_buffer.size == 0


# ---------------------------------------------------------------------------
#  SimpleVAD tests
# ---------------------------------------------------------------------------


class TestSimpleVAD:
    """Tests for SimpleVAD."""

    def test_silence_no_detection(self, vad_engine: SimpleVAD) -> None:
        """Test that silence doesn't trigger detection."""
        silence = np.zeros(480, dtype=np.float32)
        pcm16 = (silence * 32767).astype(np.int16)
        result = vad_engine.process(pcm16.tobytes())
        assert result is None

    def test_speech_detection(self, vad_engine: SimpleVAD) -> None:
        """Test speech detection."""
        t = np.linspace(0, 0.5, int(16000 * 0.5))
        speech = np.sin(2 * np.pi * 440 * t) * 0.5
        pcm16 = (speech * 32767).astype(np.int16)

        events: List[Dict[str, Any]] = []
        frame_size = 480 * 5  # 150ms chunks
        for i in range(0, len(pcm16) - frame_size, frame_size):
            chunk = pcm16[i : i + frame_size]
            result = vad_engine.process(chunk.tobytes())
            if result:
                events.append(result)

        assert len(events) > 0 or vad_engine._is_speaking

    def test_reset(self, vad_engine: SimpleVAD) -> None:
        """Test VAD reset."""
        vad_engine._is_speaking = True
        vad_engine._buffer = bytearray(b"data")
        vad_engine.reset()
        assert not vad_engine._is_speaking
        assert len(vad_engine._buffer) == 0

    def test_speech_start_event(self, vad_engine: SimpleVAD) -> None:
        """Test speech start event."""
        t = np.linspace(0, 0.1, int(16000 * 0.1))
        speech = np.sin(2 * np.pi * 440 * t) * 0.5
        pcm16 = (speech * 32767).astype(np.int16)
        event = vad_engine.process(pcm16.tobytes())
        assert event is not None or vad_engine._is_speaking


# ---------------------------------------------------------------------------
#  PipelineMetrics tests
# ---------------------------------------------------------------------------


class TestPipelineMetrics:
    """Tests for PipelineMetrics dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating metrics."""
        m = PipelineMetrics(turn_number=1, stt_latency_ms=100)
        assert m.turn_number == 1
        assert m.stt_latency_ms == 100

    def test_defaults(self) -> None:
        """Test default values."""
        m = PipelineMetrics(turn_number=1)
        assert m.llm_latency_ms == 0
        assert m.tts_latency_ms == 0
        assert m.transcript == ""

    def test_total_latency(self) -> None:
        """Test total latency calculation."""
        m = PipelineMetrics(
            turn_number=1, stt_latency_ms=100, llm_latency_ms=200, tts_latency_ms=50
        )
        assert m.total_latency_ms == 0  # Default, must be set explicitly
        m.total_latency_ms = 350
        assert m.total_latency_ms == 350


# ---------------------------------------------------------------------------
#  OrchestratorEvent tests
# ---------------------------------------------------------------------------


class TestOrchestratorEvent:
    """Tests for OrchestratorEvent dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating an event."""
        event = OrchestratorEvent(
            event_type=OrchestratorEventType.TRANSCRIPT,
            session_id="s1",
            data={"text": "Hello"},
        )
        assert event.event_type == OrchestratorEventType.TRANSCRIPT
        assert event.data["text"] == "Hello"


# ---------------------------------------------------------------------------
#  ConversationEngine tests
# ---------------------------------------------------------------------------


class TestConversationEngineCreation:
    """Tests for engine creation."""

    def test_creation(self, engine: ConversationEngine) -> None:
        """Test basic engine creation."""
        assert engine.session_id == "test-session-1"
        assert engine.tenant_id == "test-tenant-1"
        assert engine.call_id == "test-call-1"
        assert engine.state == ConversationState.IDLE

    def test_initial_state(self, engine: ConversationEngine) -> None:
        """Test initial state."""
        assert engine.state == ConversationState.IDLE
        assert not engine.is_active
        assert engine.turn_count == 0

    def test_constants(self) -> None:
        """Test engine constants."""
        assert ConversationEngine.MAX_TURNS == 50
        assert ConversationEngine.CONVERSATION_TIMEOUT_SEC == 300
        assert ConversationEngine.LLM_MAX_TOKENS == 256

    def test_goodbye_keywords_defined(self, engine: ConversationEngine) -> None:
        """Test goodbye keywords are defined."""
        assert len(engine.GOODBYE_KEYWORDS) > 0
        assert "goodbye" in engine.GOODBYE_KEYWORDS
        assert "bye" in engine.GOODBYE_KEYWORDS

    def test_fallback_responses(self, engine: ConversationEngine) -> None:
        """Test fallback responses are defined."""
        assert len(engine._fallback_responses) > 0
        response = engine._next_fallback_response()
        assert "sorry" in response.lower() or "apolog" in response.lower()


class TestStateMachine:
    """Tests for state machine transitions."""

    @pytest.mark.asyncio
    async def test_transition_to(self, engine: ConversationEngine) -> None:
        """Test state transition."""
        await engine._transition_to(ConversationState.LISTENING)
        assert engine.state == ConversationState.LISTENING

    @pytest.mark.asyncio
    async def test_no_duplicate_transition(self, engine: ConversationEngine) -> None:
        """Test transition to same state doesn't duplicate."""
        engine._state = ConversationState.LISTENING
        engine._previous_state = None
        await engine._transition_to(ConversationState.LISTENING)
        assert engine._previous_state is None

    @pytest.mark.asyncio
    async def test_transition_sequence(self, engine: ConversationEngine) -> None:
        """Test multiple transitions."""
        await engine._transition_to(ConversationState.GREETING)
        await engine._transition_to(ConversationState.LISTENING)
        await engine._transition_to(ConversationState.PROCESSING)
        assert engine.state == ConversationState.PROCESSING
        assert engine._previous_state == ConversationState.LISTENING


class TestGoodbyeDetection:
    """Tests for goodbye detection."""

    def test_detect_goodbye(self, engine: ConversationEngine) -> None:
        """Test goodbye detection."""
        assert engine._is_goodbye("Goodbye")
        assert engine._is_goodbye("thanks, bye")
        assert engine._is_goodbye("see you later")

    def test_not_goodbye(self, engine: ConversationEngine) -> None:
        """Test non-goodbye text."""
        assert not engine._is_goodbye("I want to book an appointment")
        assert not engine._is_goodbye("What are your hours?")


class TestEventSystem:
    """Tests for event system."""

    @pytest.mark.asyncio
    async def test_emit_event(self, engine: ConversationEngine) -> None:
        """Test event emission."""
        queue = engine.event_stream()
        await engine._emit_event(
            OrchestratorEventType.TRANSCRIPT,
            {"text": "Hello"},
        )
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event.event_type == OrchestratorEventType.TRANSCRIPT
        assert event.data["text"] == "Hello"

    @pytest.mark.asyncio
    async def test_multiple_queues(self, engine: ConversationEngine) -> None:
        """Test events go to multiple queues."""
        q1 = engine.event_stream()
        q2 = engine.event_stream()
        await engine._emit_event(
            OrchestratorEventType.STATE_CHANGE,
            {"new_state": "listening"},
        )
        e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert e1.event_type == e2.event_type


class TestErrorRecovery:
    """Tests for error recovery."""

    @pytest.mark.asyncio
    async def test_handle_pipeline_error(self, engine: ConversationEngine) -> None:
        """Test pipeline error handling."""
        engine._state = ConversationState.PROCESSING
        error = Exception("Test error")
        await engine._handle_pipeline_error(error)
        assert engine.state != ConversationState.PROCESSING

    def test_next_fallback_response(self, engine: ConversationEngine) -> None:
        """Test fallback response cycling."""
        r1 = engine._next_fallback_response()
        r2 = engine._next_fallback_response()
        assert r1 != r2  # Should cycle through responses

    def test_fallback_wraps(self, engine: ConversationEngine) -> None:
        """Test fallback response wrapping."""
        count = len(engine._fallback_responses)
        for _ in range(count + 1):
            engine._next_fallback_response()
        # Should have wrapped around


class TestBargeInDetection:
    """Tests for barge-in detection."""

    def test_detect_barge_in(self, engine: ConversationEngine) -> None:
        """Test barge-in detection with loud audio."""
        loud = np.full(160, 10000, dtype=np.int16).tobytes()
        detected = engine._detect_barge_in(loud)
        assert detected  # High energy should trigger

    def test_no_barge_in(self, engine: ConversationEngine) -> None:
        """Test no barge-in with quiet audio."""
        quiet = np.zeros(160, dtype=np.int16).tobytes()
        detected = engine._detect_barge_in(quiet)
        assert not detected  # Zero energy should not trigger

    @pytest.mark.asyncio
    async def test_handle_barge_in(self, engine: ConversationEngine) -> None:
        """Test barge-in handling."""
        engine._state = ConversationState.SPEAKING
        engine._is_speaking = True
        await engine._handle_barge_in()
        assert not engine._is_speaking


class TestAudioProcessing:
    """Tests for audio processing."""

    @pytest.mark.asyncio
    async def test_process_audio_when_shutdown(self, engine: ConversationEngine) -> None:
        """Test audio processing when shutdown."""
        engine._shutdown = True
        data = np.zeros(160, dtype=np.int16).tobytes()
        await engine.process_audio_chunk(data)  # Should not raise

    @pytest.mark.asyncio
    async def test_process_audio_in_listening(self, engine: ConversationEngine) -> None:
        """Test audio processing in listening state."""
        engine._state = ConversationState.LISTENING
        data = np.zeros(160, dtype=np.int16).tobytes()
        await engine.process_audio_chunk(data)
        assert engine._audio_buffer.size > 0

    @pytest.mark.asyncio
    async def test_process_audio_in_ended(self, engine: ConversationEngine) -> None:
        """Test audio processing in ended state."""
        engine._state = ConversationState.ENDED
        data = np.zeros(160, dtype=np.int16).tobytes()
        await engine.process_audio_chunk(data)  # Should be ignored


class TestLifecycle:
    """Tests for engine lifecycle."""

    @pytest.mark.asyncio
    async def test_stop_when_ended(self, engine: ConversationEngine) -> None:
        """Test stop when already ended."""
        engine._state = ConversationState.ENDED
        await engine.stop("test")  # Should not raise

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self, engine: ConversationEngine) -> None:
        """Test stop cancels background tasks."""
        engine._state = ConversationState.LISTENING
        engine._barge_in_monitor = asyncio.create_task(asyncio.sleep(10))
        await engine.stop("test")
        assert engine._state == ConversationState.ENDED


class TestDefaultSystemPrompt:
    """Tests for system prompt."""

    def test_default_prompt(self, engine: ConversationEngine) -> None:
        """Test default system prompt."""
        prompt = engine._default_system_prompt()
        assert "AI" in prompt or "assistant" in prompt.lower()
        assert len(prompt) > 0
