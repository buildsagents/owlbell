"""
Main conversation orchestrator.

Coordinates the full AI pipeline: audio in -> STT -> LLM -> TTS -> audio out.
Manages conversation state machine, turn-taking, barge-in detection,
interruption handling, pipeline coordination, error recovery,
and end-of-call detection.

Usage:
    engine = ConversationEngine(session_id, tenant_id, call_id)
    await engine.start()

    # Feed audio from FreeSWITCH
    await engine.process_audio_chunk(pcm16_bytes)

    # Listen for events
    async for event in engine.event_stream():
        handle_event(event)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Set,
)
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  State machine definitions
# ---------------------------------------------------------------------------


class ConversationState(str, Enum):
    """Finite states for conversation lifecycle."""

    IDLE = "idle"
    GREETING = "greeting"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    TRANSFERRING = "transferring"
    ENDED = "ended"


# ---------------------------------------------------------------------------
#  Event system
# ---------------------------------------------------------------------------


class OrchestratorEventType(str, Enum):
    """Event types emitted by the orchestrator."""

    STATE_CHANGE = "state_change"
    TRANSCRIPT = "transcript"
    LLM_TOKEN = "llm_token"
    TTS_AUDIO = "tts_audio"
    INTENT_DETECTED = "intent_detected"
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    METRICS = "metrics"
    BARGE_IN = "barge_in"
    CALL_END = "call_end"


@dataclass
class OrchestratorEvent:
    """Event emitted by the orchestrator.

    Attributes:
        event_type: Type of event.
        session_id: Session identifier.
        timestamp: Event timestamp (Unix epoch).
        data: Event payload data.
    """

    event_type: OrchestratorEventType
    session_id: str
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineMetrics:
    """Performance metrics for a single turn.

    Attributes:
        turn_number: Turn sequence number.
        stt_latency_ms: Speech-to-text latency.
        llm_latency_ms: LLM inference latency.
        tts_latency_ms: Text-to-speech latency.
        total_latency_ms: Total pipeline latency.
        transcript: Recognized transcript.
        response_length: LLM response character count.
        audio_duration_ms: Generated audio duration.
    """

    turn_number: int
    stt_latency_ms: int = 0
    llm_latency_ms: int = 0
    tts_latency_ms: int = 0
    total_latency_ms: int = 0
    transcript: str = ""
    response_length: int = 0
    audio_duration_ms: int = 0


# ---------------------------------------------------------------------------
#  Audio ring buffer
# ---------------------------------------------------------------------------


class AudioRingBuffer:
    """Fixed-size ring buffer for audio chunks.

    Args:
        max_size_ms: Maximum buffer size in milliseconds.
        sample_rate: Audio sample rate.
    """

    def __init__(
        self, max_size_ms: int = 30000, sample_rate: int = 16000
    ) -> None:
        self.max_size_bytes = int(max_size_ms * sample_rate * 2 / 1000)
        self._buffer = bytearray()
        self._lock = asyncio.Lock()

    async def write(self, data: bytes) -> None:
        """Write audio data to the buffer.

        Args:
            data: PCM16 audio bytes.
        """
        async with self._lock:
            self._buffer.extend(data)
            if len(self._buffer) > self.max_size_bytes:
                excess = len(self._buffer) - self.max_size_bytes
                self._buffer = self._buffer[excess:]

    async def read_all(self) -> bytes:
        """Read all buffered audio.

        Returns:
            Buffered audio bytes.
        """
        async with self._lock:
            data = bytes(self._buffer)
            self._buffer = bytearray()
            return data

    async def read_chunk(self, size_bytes: int) -> bytes:
        """Read a chunk of audio without clearing.

        Args:
            size_bytes: Bytes to read.

        Returns:
            Audio chunk.
        """
        async with self._lock:
            return bytes(self._buffer[:size_bytes])

    async def clear(self) -> None:
        """Clear the buffer."""
        async with self._lock:
            self._buffer = bytearray()

    @property
    def size(self) -> int:
        """Current buffer size in bytes."""
        return len(self._buffer)


# ---------------------------------------------------------------------------
#  VAD interface
# ---------------------------------------------------------------------------


class VADEvent:
    """Voice activity detection event."""

    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    SILENCE = "silence"


class SimpleVAD:
    """Simple energy-based VAD for the orchestrator.

    Args:
        threshold: Energy threshold for speech detection.
        min_silence_ms: Minimum silence to trigger speech end.
        min_speech_ms: Minimum speech duration.
        sample_rate: Audio sample rate.
    """

    def __init__(
        self,
        threshold: float = 0.02,
        min_silence_ms: int = 300,
        min_speech_ms: int = 250,
        sample_rate: int = 16000,
    ) -> None:
        self.threshold = threshold
        self.min_silence_ms = min_silence_ms
        self.min_speech_ms = min_speech_ms
        self.sample_rate = sample_rate
        self._is_speaking = False
        self._buffer = bytearray()
        self._silence_ms = 0.0
        self._speech_ms = 0.0

    def reset(self) -> None:
        """Reset VAD state."""
        self._is_speaking = False
        self._buffer = bytearray()
        self._silence_ms = 0.0
        self._speech_ms = 0.0

    def process(self, pcm16_bytes: bytes) -> Optional[Dict[str, Any]]:
        """Process audio chunk and detect speech events.

        Args:
            pcm16_bytes: 16-bit PCM audio.

        Returns:
            Event dict if speech start/end detected, None otherwise.
        """
        import numpy as np

        self._buffer.extend(pcm16_bytes)
        pcm = (
            np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32)
            / 32768.0
        )
        energy = np.sqrt(np.mean(pcm**2)) if len(pcm) > 0 else 0.0
        frame_duration_ms = (len(pcm) / self.sample_rate) * 1000.0

        if energy > self.threshold:
            if not self._is_speaking:
                self._is_speaking = True
                self._silence_ms = 0.0
                self._speech_ms = 0.0
                return {"type": VADEvent.SPEECH_START, "energy": float(energy)}
            self._speech_ms += frame_duration_ms
            self._silence_ms = 0.0
        else:
            if self._is_speaking:
                self._silence_ms += frame_duration_ms
                if self._silence_ms >= self.min_silence_ms:
                    if self._speech_ms >= self.min_speech_ms:
                        audio = bytes(self._buffer)
                        self.reset()
                        return {
                            "type": VADEvent.SPEECH_END,
                            "audio": audio,
                            "duration_ms": self._speech_ms,
                        }
                    self.reset()

        return None


# ---------------------------------------------------------------------------
#  Main conversation engine
# ---------------------------------------------------------------------------


class ConversationEngine:
    """Main conversation orchestrator.

    Manages the full lifecycle of an AI phone conversation:
    - State machine transitions (IDLE -> GREETING -> LISTENING -> PROCESSING -> SPEAKING)
    - Audio processing pipeline
    - Turn-taking with barge-in support
    - Tool execution
    - Event streaming to WebSocket clients
    - Error recovery and fallback responses
    - End-of-call detection (goodbye keywords, max turns, timeout)

    Args:
        session_id: Unique conversation session UUID.
        tenant_id: Business tenant UUID.
        call_id: FreeSWITCH call UUID.
        business_type: Type of business (for prompt selection).
        caller_number: Caller's phone number.
        callee_number: Number being called.
    """

    # Timing constants
    MAX_SILENCE_MS: int = 300
    MIN_SPEECH_MS: int = 250
    GREETING_TEXT: str = (
        "Hello, thank you for calling. I'm the AI assistant. "
        "How can I help you today?"
    )
    GREETING_SHORT_TEXT: str = "Hello, how can I help you?"
    MAX_TURNS: int = 50
    CONVERSATION_TIMEOUT_SEC: int = 300  # 5 minutes
    LLM_MAX_TOKENS: int = 256
    BARGE_IN_THRESHOLD: float = 0.03  # Energy threshold

    # Goodbye detection keywords
    GOODBYE_KEYWORDS: List[str] = [
        "goodbye",
        "bye",
        "see you",
        "hang up",
        "end call",
        "that's all",
        "i'm done",
        "thank you bye",
        "thanks bye",
    ]

    def __init__(
        self,
        session_id: str,
        tenant_id: str,
        call_id: str,
        business_type: str = "generic",
        caller_number: str = "",
        callee_number: str = "",
    ) -> None:
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.call_id = call_id
        self.business_type = business_type
        self.caller_number = caller_number
        self.callee_number = callee_number

        # State machine
        self._state = ConversationState.IDLE
        self._previous_state: Optional[ConversationState] = None

        # Service references (initialized in start())
        self._stt: Optional[Any] = None
        self._llm: Optional[Any] = None
        self._tts: Optional[Any] = None
        self._vad: Optional[Any] = None
        self._store: Optional[Any] = None
        self._intents: Optional[Any] = None
        self._tools: Optional[Any] = None

        # Audio
        self._audio_buffer = AudioRingBuffer(
            max_size_ms=30000, sample_rate=16000
        )
        self._vad_engine = SimpleVAD()

        # Event system
        self._event_queues: Set[asyncio.Queue] = set()
        self._event_task: Optional[asyncio.Task] = None

        # Pipeline tasks
        self._stt_task: Optional[asyncio.Task] = None
        self._llm_task: Optional[asyncio.Task] = None
        self._tts_task: Optional[asyncio.Task] = None
        self._barge_in_monitor: Optional[asyncio.Task] = None
        self._timeout_task: Optional[asyncio.Task] = None

        # Turn management
        self._turn_count: int = 0
        self._is_speaking: bool = False
        self._current_metrics: Optional[PipelineMetrics] = None

        # Conversation history for LLM context
        self._conversation_history: List[Dict[str, str]] = []

        # System prompt cache
        self._system_prompt: Optional[str] = None

        # Shutdown flag
        self._shutdown: bool = False
        self._barge_in_detected: bool = False

        # Fallback responses for error recovery
        self._fallback_responses: List[str] = [
            "I'm sorry, I didn't catch that. Could you please repeat?",
            "I seem to be having trouble hearing you. Could you say that again?",
            "My apologies, I'm having a brief issue. What did you say?",
            "I'm sorry, there was a problem. Could you repeat that for me?",
            "Pardon me, I missed that. Could you please say it again?",
        ]
        self._fallback_index: int = 0

    # ------------------------------------------------------------------ #
    #  Properties
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> ConversationState:
        """Current conversation state."""
        return self._state

    @property
    def is_active(self) -> bool:
        """Whether the conversation is active."""
        return self._state not in (
            ConversationState.IDLE,
            ConversationState.ENDED,
        )

    @property
    def turn_count(self) -> int:
        """Number of completed turns."""
        return self._turn_count

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Initialize all services and start the conversation.

        This method:
        1. Initializes all AI service references
        2. Loads business context and builds system prompt
        3. Creates the session record
        4. Plays greeting message
        5. Transitions to LISTENING state
        """
        logger.info(
            f"Starting conversation engine: session={self.session_id}, "
            f"tenant={self.tenant_id}"
        )

        # Initialize services - these will be injected or created
        await self._init_services()

        # Build system prompt
        await self._build_system_prompt()

        # Create session in store if available
        if self._store:
            try:
                await self._store.create_session(
                    session_id=self.session_id,
                    tenant_id=self.tenant_id,
                    call_id=self.call_id,
                    caller_number=self.caller_number,
                    callee_number=self.callee_number,
                    business_type=self.business_type,
                    system_prompt=self._system_prompt,
                )
            except Exception as exc:
                logger.warning(f"Failed to create session record: {exc}")

        # Play greeting and transition
        await self._transition_to(ConversationState.GREETING)
        await self._play_greeting()
        await self._transition_to(ConversationState.LISTENING)

        # Start background tasks
        self._barge_in_monitor = asyncio.create_task(
            self._barge_in_detection_loop(), name="barge_in_monitor"
        )
        self._timeout_task = asyncio.create_task(
            self._conversation_timeout(), name="timeout_monitor"
        )

        logger.info(f"Conversation engine started: session={self.session_id}")

    async def stop(self, reason: str = "ended") -> None:
        """Gracefully stop the conversation.

        Args:
            reason: Why the conversation is ending.
        """
        if self._state == ConversationState.ENDED:
            return

        logger.info(
            f"Stopping conversation: session={self.session_id}, reason={reason}"
        )
        self._shutdown = True

        # Cancel all background tasks
        for task_name, task in [
            ("stt", self._stt_task),
            ("llm", self._llm_task),
            ("tts", self._tts_task),
            ("barge_in", self._barge_in_monitor),
            ("timeout", self._timeout_task),
        ]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # End session in store
        if self._store:
            try:
                await self._store.end_session(self.session_id, reason)
            except Exception as exc:
                logger.warning(f"Failed to end session record: {exc}")

        # Final state transition
        await self._transition_to(ConversationState.ENDED)

        # Emit final event
        await self._emit_event(OrchestratorEventType.CALL_END, {
            "state": "ended",
            "reason": reason,
            "turns": self._turn_count,
        })

        # Clean up event queues
        self._event_queues.clear()

        logger.info(f"Conversation engine stopped: session={self.session_id}")

    async def _init_services(self) -> None:
        """Initialize AI service references with lazy imports."""
        try:
            from backend.ai.stt.whisper_service import get_whisper_service
            self._stt = await get_whisper_service()
        except Exception as exc:
            logger.warning(f"STT service not available: {exc}")

        try:
            from backend.ai.llm.ollama_client import get_ollama_client
            self._llm = await get_ollama_client()
        except Exception as exc:
            logger.warning(f"LLM service not available: {exc}")

        try:
            from backend.ai.tts.piper_service import get_piper_service
            self._tts = await get_piper_service()
        except Exception as exc:
            logger.warning(f"TTS service not available: {exc}")

        try:
            from backend.ai.memory.conversation_store import (
                get_conversation_store,
            )
            self._store = await get_conversation_store()
        except Exception as exc:
            logger.warning(f"Conversation store not available: {exc}")

        try:
            from backend.ai.intents.classifier import get_intent_classifier
            self._intents = await get_intent_classifier()
        except Exception as exc:
            logger.warning(f"Intent classifier not available: {exc}")

        try:
            from backend.ai.tools.registry import get_tool_registry
            self._tools = await get_tool_registry()
        except Exception as exc:
            logger.warning(f"Tool registry not available: {exc}")

    async def _build_system_prompt(self) -> None:
        """Build system prompt with business context."""
        if self._llm:
            try:
                business_ctx = {"name": "the business", "type": self.business_type}
                if self._store:
                    try:
                        ctx = await self._store.get_business_context(
                            self.tenant_id
                        )
                        if ctx:
                            business_ctx = ctx
                    except Exception:
                        pass

                available_tools = (
                    self._tools.get_tool_descriptions()
                    if self._tools
                    else []
                )

                self._system_prompt = self._llm.build_system_prompt(
                    business_context=business_ctx,
                    available_tools=available_tools,
                )
            except Exception as exc:
                logger.warning(f"Failed to build system prompt: {exc}")
                self._system_prompt = self._default_system_prompt()
        else:
            self._system_prompt = self._default_system_prompt()

    def _default_system_prompt(self) -> str:
        """Return a default system prompt."""
        return (
            "You are a professional AI phone assistant. You are friendly, "
            "efficient, and helpful. Keep responses concise (2-3 sentences). "
            "Always confirm important details. If unsure, say you'll take a message. "
            "If the caller asks for a human, offer to transfer immediately."
        )

    # ------------------------------------------------------------------ #
    #  State machine
    # ------------------------------------------------------------------ #

    async def _transition_to(self, new_state: ConversationState) -> None:
        """Transition to a new conversation state.

        Args:
            new_state: Target state.
        """
        if self._state == new_state:
            return

        old_state = self._state
        self._previous_state = old_state
        self._state = new_state

        logger.info(
            f"State: {old_state.value} -> {new_state.value} "
            f"(session={self.session_id})"
        )

        # Persist state change
        if self._store:
            try:
                await self._store.update_session_state(
                    self.session_id, new_state.value
                )
            except Exception as exc:
                logger.debug(f"Failed to persist state: {exc}")

        # Emit event
        await self._emit_event(
            OrchestratorEventType.STATE_CHANGE,
            {
                "previous_state": old_state.value,
                "new_state": new_state.value,
            },
        )

    # ------------------------------------------------------------------ #
    #  Event system
    # ------------------------------------------------------------------ #

    async def _emit_event(
        self, event_type: OrchestratorEventType, data: Dict[str, Any]
    ) -> None:
        """Emit an event to all registered event queues.

        Args:
            event_type: Type of event.
            data: Event payload.
        """
        event = OrchestratorEvent(
            type=event_type,
            session_id=self.session_id,
            data=data,
        )

        closed_queues: Set[asyncio.Queue] = set()
        for queue in self._event_queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                closed_queues.add(queue)

        self._event_queues -= closed_queues

    def event_stream(self) -> asyncio.Queue:
        """Get an event queue for consuming orchestrator events.

        Returns:
            Asyncio queue that receives events.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._event_queues.add(queue)
        return queue

    # ------------------------------------------------------------------ #
    #  Greeting
    # ------------------------------------------------------------------ #

    async def _play_greeting(self) -> None:
        """Play the greeting message via TTS."""
        greeting = (
            self.GREETING_SHORT_TEXT
            if self._turn_count > 0
            else self.GREETING_TEXT
        )

        await self._emit_event(
            OrchestratorEventType.LLM_TOKEN,
            {"text": greeting, "is_greeting": True},
        )

        if self._tts:
            try:
                result = await self._tts.synthesize(greeting)
                await self._emit_event(
                    OrchestratorEventType.TTS_AUDIO,
                    {
                        "audio_pcm16": result.pcm16.tobytes().hex(),
                        "sample_rate": result.sample_rate,
                        "duration_ms": result.duration_ms,
                        "text": greeting,
                        "is_final": True,
                    },
                )
            except Exception as exc:
                logger.warning(f"Failed to synthesize greeting: {exc}")

        # Store greeting message
        if self._store:
            try:
                await self._store.add_message(
                    session_id=self.session_id,
                    role="assistant",
                    content=greeting,
                    sequence=0,
                )
            except Exception as exc:
                logger.debug(f"Failed to store greeting: {exc}")

    # ------------------------------------------------------------------ #
    #  Audio processing
    # ------------------------------------------------------------------ #

    async def process_audio_chunk(self, pcm16_bytes: bytes) -> None:
        """Process incoming audio from FreeSWITCH.

        Called for each audio chunk received during the call.
        In LISTENING state, feeds audio to VAD. In SPEAKING state,
        monitors for barge-in.

        Args:
            pcm16_bytes: 16-bit PCM audio (8kHz, mono from FreeSWITCH).
        """
        if self._shutdown or self._state == ConversationState.ENDED:
            return

        # Buffer audio
        await self._audio_buffer.write(pcm16_bytes)

        # Feed to VAD if in listening state
        if self._state == ConversationState.LISTENING:
            event = self._vad_engine.process(pcm16_bytes)
            if event:
                await self._handle_vad_event(event)

        # Monitor for barge-in if speaking
        elif self._state == ConversationState.SPEAKING:
            if self._detect_barge_in(pcm16_bytes):
                await self._handle_barge_in()

    async def _handle_vad_event(self, event: Dict[str, Any]) -> None:
        """Handle VAD speech detection events.

        Args:
            event: VAD event dict.
        """
        event_type = event.get("type")

        if event_type == VADEvent.SPEECH_START:
            logger.debug("VAD: speech_start detected")

        elif event_type == VADEvent.SPEECH_END:
            logger.debug("VAD: speech_end detected")
            audio_data = event.get("audio")
            if audio_data:
                # Start processing pipeline in background
                asyncio.create_task(self._process_turn(audio_data))

    def _detect_barge_in(self, pcm16_bytes: bytes) -> bool:
        """Detect caller speaking during TTS playback.

        Args:
            pcm16_bytes: Current audio chunk.

        Returns:
            True if barge-in detected.
        """
        import numpy as np

        pcm = (
            np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32)
            / 32768.0
        )
        energy = np.sqrt(np.mean(pcm**2)) if len(pcm) > 0 else 0.0
        return energy > self.BARGE_IN_THRESHOLD

    async def _handle_barge_in(self) -> None:
        """Handle barge-in: stop speaking, reset pipeline, return to listening."""
        if not self._is_speaking:
            return

        logger.info(f"Barge-in detected: session={self.session_id}")
        self._barge_in_detected = True
        self._is_speaking = False

        # Cancel ongoing tasks
        for task_name, task in [
            ("tts", self._tts_task),
            ("llm", self._llm_task),
        ]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                setattr(self, f"_{task_name}_task", None)

        await self._emit_event(
            OrchestratorEventType.BARGE_IN,
            {"timestamp": time.time()},
        )

        # Return to listening
        await self._transition_to(ConversationState.LISTENING)

    async def _barge_in_detection_loop(self) -> None:
        """Background task for continuous barge-in monitoring."""
        try:
            while not self._shutdown:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    async def _conversation_timeout(self) -> None:
        """Monitor conversation duration and end if exceeded."""
        try:
            await asyncio.sleep(self.CONVERSATION_TIMEOUT_SEC)
            if self.is_active and not self._shutdown:
                logger.info(
                    f"Conversation timeout after "
                    f"{self.CONVERSATION_TIMEOUT_SEC}s"
                )
                await self._speak(
                    "I haven't heard from you in a while, so I'll end this call. "
                    "Feel free to call back anytime. Goodbye!"
                )
                await self.stop("timeout")
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------ #
    #  Main turn processing
    # ------------------------------------------------------------------ #

    async def _process_turn(self, audio_data: bytes) -> None:
        """Process a complete caller utterance through the full pipeline.

        Pipeline: Audio -> STT -> Intent -> LLM -> TTS -> Audio

        Args:
            audio_data: Complete utterance audio (PCM16, 16kHz).
        """
        if self._state not in (
            ConversationState.LISTENING,
            ConversationState.GREETING,
        ):
            logger.warning(
                f"Ignoring turn, state={self._state.value}"
            )
            return

        await self._transition_to(ConversationState.PROCESSING)

        self._turn_count += 1
        if self._turn_count > self.MAX_TURNS:
            logger.info(f"Max turns ({self.MAX_TURNS}) reached, ending")
            await self._speak(
                "I'm sorry, but I need to end this call now. "
                "Please call back if you need further assistance. Goodbye."
            )
            await self.stop("max_turns")
            return

        metrics = PipelineMetrics(turn_number=self._turn_count)
        self._current_metrics = metrics

        try:
            # === STT Phase ===
            transcript = ""
            if self._stt:
                stt_start = time.perf_counter()
                try:
                    stt_result = await self._stt.transcribe(audio_data)
                    metrics.stt_latency_ms = int(
                        (time.perf_counter() - stt_start) * 1000
                    )
                    transcript = stt_result.text.strip()
                    metrics.transcript = transcript

                    await self._emit_event(
                        OrchestratorEventType.TRANSCRIPT,
                        {
                            "text": transcript,
                            "confidence": getattr(stt_result, "confidence", 0.0),
                            "latency_ms": metrics.stt_latency_ms,
                        },
                    )
                except Exception as exc:
                    logger.error(f"STT error: {exc}")
                    await self._handle_pipeline_error(exc)
                    return
            else:
                logger.warning("STT service not available")
                await self._transition_to(ConversationState.LISTENING)
                return

            if not transcript:
                logger.debug("Empty transcript, returning to listening")
                await self._transition_to(ConversationState.LISTENING)
                return

            logger.info(
                f"Turn {self._turn_count}: '{transcript[:80]}...' "
                if len(transcript) > 80
                else f"Turn {self._turn_count}: '{transcript}'"
            )

            # Check for goodbye
            if self._is_goodbye(transcript):
                await self._speak("Thank you for calling. Have a great day! Goodbye.")
                await self.stop("hangup")
                return

            # Store user message
            if self._store:
                try:
                    await self._store.add_message(
                        session_id=self.session_id,
                        role="user",
                        content=transcript,
                        sequence=self._turn_count * 2 - 1,
                        stt_latency_ms=metrics.stt_latency_ms,
                    )
                except Exception as exc:
                    logger.debug(f"Failed to store user message: {exc}")

            # === Intent Detection Phase ===
            intent_result = None
            if self._intents:
                try:
                    intent_result = await self._intents.classify(transcript)
                    await self._emit_event(
                        OrchestratorEventType.INTENT_DETECTED,
                        {
                            "intent": intent_result.intent_type.value,
                            "confidence": intent_result.confidence,
                            "method": intent_result.method,
                            "entities": intent_result.entities,
                        },
                    )

                    # Handle direct intent actions
                    if intent_result.intent_type.value == "transfer_call":
                        if self._tools:
                            xfer_result = await self._tools.execute(
                                "transfer_call",
                                {
                                    "destination": "human",
                                    "reason": transcript,
                                },
                            )
                            await self._speak(xfer_result.data.get("message", "Transferring you now."))
                            await self._transition_to(
                                ConversationState.TRANSFERRING
                            )
                            return

                    elif intent_result.intent_type.value == "end_call":
                        await self._speak("Goodbye! Have a wonderful day.")
                        await self.stop("hangup")
                        return

                except Exception as exc:
                    logger.warning(f"Intent classification error: {exc}")

            # === LLM Phase ===
            llm_text = ""
            llm_tool_calls: List[Dict[str, Any]] = []

            if self._llm:
                llm_start = time.perf_counter()
                try:
                    # Build messages with history
                    messages = self._llm.build_messages_with_history(
                        session_id=self.session_id,
                        system_prompt=self._system_prompt or "",
                        new_user_message=transcript,
                    )

                    # Get available tools
                    available_tools = (
                        self._tools.get_tool_descriptions()
                        if self._tools
                        else []
                    )

                    # Run LLM
                    llm_response = await self._llm.chat(
                        messages=messages,
                        tools=available_tools if available_tools else None,
                        max_tokens=self.LLM_MAX_TOKENS,
                    )

                    metrics.llm_latency_ms = int(
                        (time.perf_counter() - llm_start) * 1000
                    )
                    llm_text = llm_response.content
                    metrics.response_length = len(llm_text)
                    llm_tool_calls = llm_response.tool_calls

                    # Stream LLM tokens for real-time display
                    await self._emit_event(
                        OrchestratorEventType.LLM_TOKEN,
                        {
                            "text": llm_text,
                            "is_complete": True,
                            "latency_ms": metrics.llm_latency_ms,
                        },
                    )

                except Exception as exc:
                    logger.error(f"LLM error: {exc}")
                    await self._handle_pipeline_error(exc)
                    return
            else:
                # Fallback response if LLM unavailable
                llm_text = self._next_fallback_response()

            # Store assistant message
            if self._store:
                try:
                    await self._store.add_message(
                        session_id=self.session_id,
                        role="assistant",
                        content=llm_text,
                        sequence=self._turn_count * 2,
                        llm_latency_ms=metrics.llm_latency_ms,
                    )
                except Exception as exc:
                    logger.debug(f"Failed to store assistant message: {exc}")

            # Update conversation history
            self._conversation_history.append(
                {"role": "user", "content": transcript}
            )
            self._conversation_history.append(
                {"role": "assistant", "content": llm_text}
            )

            # === Tool Call Phase ===
            if llm_tool_calls and self._tools:
                for tool_call in llm_tool_calls:
                    await self._execute_tool(tool_call)
                    return

            # === TTS Phase ===
            if llm_text:
                await self._transition_to(ConversationState.SPEAKING)
                await self._speak(llm_text)

            # Calculate and emit metrics
            metrics.total_latency_ms = (
                metrics.stt_latency_ms
                + metrics.llm_latency_ms
                + metrics.tts_latency_ms
            )

            await self._emit_event(
                OrchestratorEventType.METRICS,
                {
                    "turn": metrics.turn_number,
                    "stt_ms": metrics.stt_latency_ms,
                    "llm_ms": metrics.llm_latency_ms,
                    "tts_ms": metrics.tts_latency_ms,
                    "total_ms": metrics.total_latency_ms,
                },
            )

            # Store metrics
            if self._store:
                try:
                    await self._store.update_session_metrics(
                        self.session_id, metrics
                    )
                except Exception as exc:
                    logger.debug(f"Failed to store metrics: {exc}")

            # Return to listening
            if self._state != ConversationState.ENDED:
                await self._transition_to(ConversationState.LISTENING)

        except Exception as exc:
            logger.exception(f"Pipeline error in turn {self._turn_count}: {exc}")
            await self._handle_pipeline_error(exc)

    async def _speak(self, text: str) -> None:
        """Synthesize and play text using TTS.

        Uses sentence-level synthesis. Monitors for barge-in during playback.

        Args:
            text: Text to speak.
        """
        if not text or not text.strip():
            return

        self._is_speaking = True
        tts_start = time.perf_counter()
        total_audio_duration = 0

        try:
            if self._tts:
                # Split into sentences and synthesize each
                import re

                sentences = re.split(r"(?<=[.!?])\s+", text)

                for sentence in sentences:
                    if not self._is_speaking or self._shutdown:
                        break

                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    try:
                        result = await self._tts.synthesize(sentence)

                        # Emit audio event for playback
                        await self._emit_event(
                            OrchestratorEventType.TTS_AUDIO,
                            {
                                "audio_pcm16": result.pcm16.tobytes().hex(),
                                "sample_rate": result.sample_rate,
                                "duration_ms": result.duration_ms,
                                "text": sentence,
                                "is_final": sentence == sentences[-1],
                            },
                        )

                        total_audio_duration += result.duration_ms

                        # Wait for playback duration
                        playback_time = result.duration_ms / 1000.0
                        await asyncio.sleep(playback_time)

                    except Exception as exc:
                        logger.error(f"TTS synthesis error: {exc}")
                        continue
            else:
                logger.warning("TTS service not available")

        finally:
            if self._current_metrics:
                self._current_metrics.tts_latency_ms = int(
                    (time.perf_counter() - tts_start) * 1000
                )
                self._current_metrics.audio_duration_ms = total_audio_duration

            self._is_speaking = False

    async def _execute_tool(self, tool_call: Dict[str, Any]) -> None:
        """Execute a tool requested by the LLM.

        Args:
            tool_call: Tool call specification from LLM.
        """
        tool_name = tool_call.get("name", "")
        parameters = tool_call.get("parameters", {})

        logger.info(f"Executing tool: {tool_name}({parameters})")

        await self._emit_event(
            OrchestratorEventType.TOOL_CALLED,
            {"tool": tool_name, "parameters": parameters},
        )

        if not self._tools:
            logger.warning("Tool registry not available")
            return

        try:
            result = await self._tools.execute(
                tool_name=tool_name,
                parameters=parameters,
                tenant_id=self.tenant_id,
                session_id=self.session_id,
            )

            await self._emit_event(
                OrchestratorEventType.TOOL_RESULT,
                {
                    "tool": tool_name,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error_message,
                },
            )

            # Speak tool result
            if result.success and result.data:
                message = result.data.get(
                    "message",
                    result.data.get(
                        "confirmation",
                        f"Done. {result.to_llm_text()[:100]}",
                    ),
                )
                if message:
                    await self._speak(message)
            elif not result.success:
                await self._speak(
                    "I apologize, I had trouble with that request. "
                    "Could you try again?"
                )

        except Exception as exc:
            logger.error(f"Tool execution error: {exc}")
            await self._emit_event(
                OrchestratorEventType.ERROR,
                {
                    "component": "tools",
                    "error": str(exc),
                    "tool": tool_name,
                },
            )

        # Return to listening
        if self._state != ConversationState.ENDED:
            await self._transition_to(ConversationState.LISTENING)

    # ------------------------------------------------------------------ #
    #  Error recovery
    # ------------------------------------------------------------------ #

    async def _handle_pipeline_error(self, error: Exception) -> None:
        """Handle pipeline errors with graceful recovery.

        Args:
            error: The exception that occurred.
        """
        logger.exception(f"Pipeline error: {error}")

        await self._emit_event(
            OrchestratorEventType.ERROR,
            {
                "component": "pipeline",
                "error_type": type(error).__name__,
                "error_message": str(error),
                "recoverable": True,
            },
        )

        # Try to recover by speaking a fallback response
        try:
            fallback = self._next_fallback_response()
            await self._speak(fallback)
        except Exception as exc:
            logger.error(f"Fallback response failed: {exc}")

        # Return to listening
        if self._state != ConversationState.ENDED:
            await self._transition_to(ConversationState.LISTENING)

    def _next_fallback_response(self) -> str:
        """Get the next fallback response, cycling through options.

        Returns:
            Fallback response string.
        """
        response = self._fallback_responses[
            self._fallback_index % len(self._fallback_responses)
        ]
        self._fallback_index += 1
        return response

    # ------------------------------------------------------------------ #
    #  Goodbye detection
    # ------------------------------------------------------------------ #

    def _is_goodbye(self, text: str) -> bool:
        """Detect if the user is saying goodbye.

        Args:
            text: User utterance.

        Returns:
            True if goodbye detected.
        """
        text_lower = text.lower().strip()
        return any(keyword in text_lower for keyword in self.GOODBYE_KEYWORDS)

    # ------------------------------------------------------------------ #
    #  Streaming interface
    # ------------------------------------------------------------------ #

    async def process_transcript(self, transcript: str) -> None:
        """Process a text transcript directly (bypass STT).

        Useful for testing or text-based interfaces.

        Args:
            transcript: User utterance text.
        """
        if self._state != ConversationState.LISTENING:
            logger.warning(
                f"Cannot process transcript in state {self._state.value}"
            )
            return

        # Simulate a turn with the transcript
        await self._transition_to(ConversationState.PROCESSING)

        # Emit transcript event
        await self._emit_event(
            OrchestratorEventType.TRANSCRIPT,
            {"text": transcript, "confidence": 1.0, "latency_ms": 0},
        )

        # Store message
        self._turn_count += 1
        if self._store:
            try:
                await self._store.add_message(
                    session_id=self.session_id,
                    role="user",
                    content=transcript,
                    sequence=self._turn_count * 2 - 1,
                )
            except Exception:
                pass

        # Process through LLM
        if self._llm:
            try:
                messages = self._llm.build_messages_with_history(
                    session_id=self.session_id,
                    system_prompt=self._system_prompt or "",
                    new_user_message=transcript,
                )

                available_tools = (
                    self._tools.get_tool_descriptions() if self._tools else []
                )

                llm_response = await self._llm.chat(
                    messages=messages,
                    tools=available_tools if available_tools else None,
                    max_tokens=self.LLM_MAX_TOKENS,
                )

                # Store and speak response
                if self._store:
                    try:
                        await self._store.add_message(
                            session_id=self.session_id,
                            role="assistant",
                            content=llm_response.content,
                            sequence=self._turn_count * 2,
                        )
                    except Exception:
                        pass

                self._conversation_history.append(
                    {"role": "user", "content": transcript}
                )
                self._conversation_history.append(
                    {"role": "assistant", "content": llm_response.content}
                )

                # Handle tool calls
                if llm_response.tool_calls and self._tools:
                    for tool_call in llm_response.tool_calls:
                        await self._execute_tool(tool_call)
                    return

                # Speak response
                await self._transition_to(ConversationState.SPEAKING)
                await self._speak(llm_response.content)

            except Exception as exc:
                logger.error(f"Direct transcript processing error: {exc}")
                await self._speak(self._next_fallback_response())

        # Return to listening
        if self._state != ConversationState.ENDED:
            await self._transition_to(ConversationState.LISTENING)

    async def event_consumer(self) -> AsyncGenerator[OrchestratorEvent, None]:
        """Consume events from the orchestrator.

        Yields:
            OrchestratorEvent objects.
        """
        queue = self.event_stream()
        try:
            while self._state != ConversationState.ENDED:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield event
                except asyncio.TimeoutError:
                    continue
        finally:
            self._event_queues.discard(queue)
