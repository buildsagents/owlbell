"""
Tests for Whisper STT service.

Covers transcription, streaming, VAD integration, confidence scoring,
and error handling.
"""

from __future__ import annotations

import asyncio
import struct
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from backend.ai.stt.whisper_service import (
    STTResult,
    VADEngine,
    VADSegment,
    WhisperService,
    WhisperServiceError,
    WhisperServiceUnavailable,
    WhisperTranscriptionError,
)
from backend.ai.tts.piper_service import G711Codec


# ---------------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def whisper_service() -> WhisperService:
    """Create a WhisperService for testing."""
    return WhisperService(
        base_url="http://localhost:9999",
        timeout=5.0,
        max_retries=2,
        retry_delay=0.1,
    )


@pytest.fixture
def sample_pcm16() -> np.ndarray:
    """Generate sample PCM16 audio (sine wave)."""
    sample_rate = 16000
    duration = 1.0  # 1 second
    t = np.linspace(0, duration, int(sample_rate * duration))
    sine_wave = np.sin(2 * np.pi * 440 * t) * 0.5
    return (sine_wave * 32767).astype(np.int16)


@pytest.fixture
def vad_engine() -> VADEngine:
    """Create a VAD engine for testing."""
    return VADEngine(threshold=0.02, min_silence_ms=200, min_speech_ms=150)


# ---------------------------------------------------------------------------
#  STTResult tests
# ---------------------------------------------------------------------------


class TestSTTResult:
    """Tests for STTResult dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a basic STTResult."""
        result = STTResult(text="hello world", confidence=0.95)
        assert result.text == "hello world"
        assert result.confidence == 0.95
        assert result.language == "en"
        assert not result.is_partial

    def test_is_empty_with_text(self) -> None:
        """Test is_empty with non-empty text."""
        result = STTResult(text="hello")
        assert not result.is_empty

    def test_is_empty_with_whitespace(self) -> None:
        """Test is_empty with whitespace-only text."""
        result = STTResult(text="   ")
        assert result.is_empty

    def test_is_empty_with_none(self) -> None:
        """Test is_empty with empty text."""
        result = STTResult(text="")
        assert result.is_empty

    def test_word_count(self) -> None:
        """Test word count calculation."""
        result = STTResult(text="hello world foo bar")
        assert result.word_count == 4

    def test_word_count_empty(self) -> None:
        """Test word count with empty text."""
        result = STTResult(text="")
        assert result.word_count == 0

    def test_defaults(self) -> None:
        """Test default field values."""
        result = STTResult(text="test")
        assert result.confidence == 0.0
        assert result.language == "en"
        assert result.segments == []
        assert result.processing_time_ms == 0
        assert result.sequence == 0


# ---------------------------------------------------------------------------
#  VADEngine tests
# ---------------------------------------------------------------------------


class TestVADEngine:
    """Tests for VADEngine."""

    def test_creation(self, vad_engine: VADEngine) -> None:
        """Test VAD engine creation."""
        assert vad_engine.threshold == 0.02
        assert vad_engine.min_silence_ms == 200
        assert vad_engine.min_speech_ms == 150

    def test_reset(self, vad_engine: VADEngine) -> None:
        """Test VAD reset."""
        vad_engine._is_speaking = True
        vad_engine._speech_buffer = bytearray(b"data")
        vad_engine.reset()
        assert not vad_engine._is_speaking
        assert vad_engine._speech_buffer == bytearray()

    def test_silence_no_detection(self, vad_engine: VADEngine) -> None:
        """Test that silence doesn't trigger detection."""
        # Create low-energy (silent) audio
        silence = np.zeros(480, dtype=np.float32)  # 30ms at 16kHz
        pcm16 = (silence * 32767).astype(np.int16)
        result = vad_engine.process(pcm16.tobytes())
        assert result is None

    def test_speech_detection(self, vad_engine: VADEngine) -> None:
        """Test speech detection with high-energy audio."""
        # Create high-energy (speech-like) audio - multiple frames needed
        t = np.linspace(0, 0.5, int(16000 * 0.5))  # 500ms
        speech = np.sin(2 * np.pi * 440 * t) * 0.5
        pcm16 = (speech * 32767).astype(np.int16)

        # Feed multiple frames
        frame_size = 480 * 10  # ~300ms chunks
        segment = None
        for i in range(0, len(pcm16) - frame_size, frame_size):
            chunk = pcm16[i : i + frame_size]
            result = vad_engine.process(chunk.tobytes())
            if result is not None:
                segment = result
                break

        # Should detect speech start at some point
        assert vad_engine._is_speaking or segment is not None

    def test_speech_segment_result(self, vad_engine: VADEngine) -> None:
        """Test VAD segment output."""
        speech = np.sin(2 * np.pi * 440 * np.linspace(0, 0.3, int(16000 * 0.3)))
        pcm16 = (speech * 32767).astype(np.int16)
        vad_engine._is_speaking = True
        vad_engine._speech_duration_ms = 200  # Above min_speech_ms
        result = vad_engine.process(pcm16.tobytes())
        # Should return a segment or None depending on silence state
        if result is not None:
            assert isinstance(result, VADSegment)
            assert isinstance(result.speech, bytes)


# ---------------------------------------------------------------------------
#  WhisperService tests
# ---------------------------------------------------------------------------


class TestWhisperService:
    """Tests for WhisperService."""

    @pytest.mark.asyncio
    async def test_start_stop(self, whisper_service: WhisperService) -> None:
        """Test service start and stop lifecycle."""
        with patch.object(
            whisper_service, "health_check", new_callable=AsyncMock
        ) as mock_health:
            mock_health.return_value = True
            with patch(
                "asyncio.create_task"
            ) as mock_create:
                mock_task = MagicMock()
                mock_create.return_value = mock_task
                await whisper_service.start()
                assert whisper_service._session is not None
                mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cleanup(self, whisper_service: WhisperService) -> None:
        """Test that stop cleans up resources."""
        whisper_service._session = MagicMock()
        whisper_service._session.closed = False
        whisper_service._session.close = AsyncMock()
        whisper_service._health_check_task = None

        await whisper_service.stop()
        whisper_service._session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_success(
        self, whisper_service: WhisperService
    ) -> None:
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status = 200

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.get.return_value = mock_cm

        whisper_service._session = mock_session

        result = await whisper_service.health_check()
        assert result is True
        assert whisper_service.is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(
        self, whisper_service: WhisperService
    ) -> None:
        """Test failed health check."""
        mock_response = MagicMock()
        mock_response.status = 500

        mock_session = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.get.return_value = mock_cm

        whisper_service._session = mock_session

        result = await whisper_service.health_check()
        assert result is False

    def test_prepare_wav_from_bytes(self, whisper_service: WhisperService) -> None:
        """Test WAV preparation from bytes."""
        pcm16 = np.zeros(16000, dtype=np.int16)
        wav = whisper_service._prepare_wav(pcm16.tobytes(), sample_rate=16000)
        assert isinstance(wav, bytes)
        assert len(wav) > 44  # WAV header is 44 bytes

    def test_prepare_wav_from_numpy(self, whisper_service: WhisperService) -> None:
        """Test WAV preparation from numpy array."""
        pcm16 = np.zeros(16000, dtype=np.int16)
        wav = whisper_service._prepare_wav(pcm16, sample_rate=16000)
        assert isinstance(wav, bytes)
        assert len(wav) > 44

    def test_resample_8k_to_16k(self, whisper_service: WhisperService) -> None:
        """Test 8kHz to 16kHz resampling."""
        pcm8k = np.sin(2 * np.pi * 440 * np.linspace(0, 1.0, 8000))
        pcm8k = (pcm8k * 32767).astype(np.int16)
        pcm16k = whisper_service._resample_8k_to_16k(pcm8k)
        assert len(pcm16k) == 16000  # Doubled sample count
        assert pcm16k.dtype == np.int16

    def test_calculate_confidence_no_segments(
        self, whisper_service: WhisperService
    ) -> None:
        """Test confidence with no segments."""
        confidence = whisper_service._calculate_confidence([])
        assert confidence == 0.0

    def test_calculate_confidence_with_segments(
        self, whisper_service: WhisperService
    ) -> None:
        """Test confidence calculation with segments."""
        segments = [
            {"avg_logprob": -0.5},
            {"avg_logprob": -0.8},
        ]
        confidence = whisper_service._calculate_confidence(segments)
        assert 0.0 <= confidence <= 1.0

    def test_calculate_confidence_good_quality(
        self, whisper_service: WhisperService
    ) -> None:
        """Test confidence with good quality segments."""
        segments = [
            {"avg_logprob": -0.5},
            {"avg_logprob": -0.3},
        ]
        confidence = whisper_service._calculate_confidence(segments)
        assert confidence > 0.5  # Good quality should be > 0.5

    def test_pcm_to_float(self, whisper_service: WhisperService) -> None:
        """Test PCM to float conversion."""
        pcm16 = np.array([0, 16384, -16384, 32767, -32768], dtype=np.int16)
        float_audio = whisper_service.pcm_to_float(pcm16)
        assert float_audio.dtype == np.float32
        assert abs(float_audio[1] - 0.5) < 0.01
        assert abs(float_audio[2] + 0.5) < 0.01

    def test_float_to_pcm(self, whisper_service: WhisperService) -> None:
        """Test float to PCM conversion."""
        float_audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        pcm16 = whisper_service.float_to_pcm(float_audio)
        assert pcm16.dtype == np.int16
        assert pcm16[3] == 32767  # Clipped to max
        assert pcm16[4] == -32767  # Clipped to min

    def test_apply_gain(self, whisper_service: WhisperService) -> None:
        """Test gain application."""
        pcm16 = np.array([1000, -1000], dtype=np.int16)
        gained = whisper_service.apply_gain(pcm16, 6.0)  # ~2x gain
        assert len(gained) == 2
        assert abs(gained[0]) > abs(pcm16[0])

    def test_normalize_audio(self, whisper_service: WhisperService) -> None:
        """Test audio normalization."""
        # Quiet audio
        pcm16 = np.array([100, -100, 50, -50], dtype=np.int16)
        normalized = whisper_service.normalize_audio(pcm16, target_db=-20.0)
        assert len(normalized) == 4
        assert normalized.dtype == np.int16

    @pytest.mark.asyncio
    async def test_transcribe_unhealthy_server(
        self, whisper_service: WhisperService, sample_pcm16: np.ndarray
    ) -> None:
        """Test transcription when server is unhealthy."""
        whisper_service._is_healthy = False
        with patch.object(
            whisper_service, "health_check", new_callable=AsyncMock
        ) as mock_health:
            mock_health.return_value = False
            with pytest.raises(WhisperServiceUnavailable):
                await whisper_service.transcribe(sample_pcm16)

    @pytest.mark.asyncio
    async def test_transcribe_streaming(
        self, whisper_service: WhisperService
    ) -> None:
        """Test streaming transcription."""
        whisper_service._is_healthy = True

        async def audio_gen() -> AsyncGenerator[bytes, None]:
            for _ in range(3):
                pcm16 = np.zeros(32000, dtype=np.int16)  # 1s at 16kHz
                yield pcm16.tobytes()

        with patch.object(
            whisper_service, "transcribe", new_callable=AsyncMock
        ) as mock_transcribe:
            mock_transcribe.return_value = STTResult(
                text="hello", confidence=0.9
            )
            results = []
            async for result in whisper_service.transcribe_streaming(
                audio_gen()
            ):
                results.append(result)

            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_transcribe_8khz(
        self, whisper_service: WhisperService
    ) -> None:
        """Test 8kHz transcription with automatic resampling."""
        whisper_service._is_healthy = True
        pcm8k = np.zeros(8000, dtype=np.int16)  # 1s at 8kHz

        with patch.object(
            whisper_service, "transcribe", new_callable=AsyncMock
        ) as mock_transcribe:
            mock_transcribe.return_value = STTResult(
                text="hello", confidence=0.9
            )
            result = await whisper_service.transcribe_8khz(pcm8k)
            assert result.text == "hello"
            # Verify resampled to 16kHz
            call_args = mock_transcribe.call_args
            assert call_args[1]["sample_rate"] == 16000


# ---------------------------------------------------------------------------
#  G.711 Codec tests
# ---------------------------------------------------------------------------


class TestG711Codec:
    """Tests for G.711 codec conversion."""

    def test_pcm_to_mulaw_roundtrip(self) -> None:
        """Test PCM -> mu-law -> PCM roundtrip."""
        pcm16 = np.array(
            [0, 1000, -1000, 5000, -5000, 16000, -16000], dtype=np.int16
        )
        mulaw = G711Codec.pcm_to_mulaw(pcm16)
        assert isinstance(mulaw, bytes)
        assert len(mulaw) == len(pcm16)

        # Decode back
        pcm_decoded = G711Codec.mulaw_to_pcm(mulaw)
        assert len(pcm_decoded) == len(pcm16)
        assert pcm_decoded.dtype == np.int16

    def test_pcm_to_alaw(self) -> None:
        """Test PCM to A-law conversion."""
        pcm16 = np.array([0, 1000, -1000, 5000, -5000], dtype=np.int16)
        alaw = G711Codec.pcm_to_alaw(pcm16)
        assert isinstance(alaw, bytes)
        assert len(alaw) == len(pcm16)

    def test_mulaw_silence(self) -> None:
        """Test mu-law encoding of silence."""
        pcm16 = np.zeros(100, dtype=np.int16)
        mulaw = G711Codec.pcm_to_mulaw(pcm16)
        decoded = G711Codec.mulaw_to_pcm(mulaw)
        # Silence should remain close to zero
        assert np.all(np.abs(decoded) < 100)

    def test_mulaw_max_values(self) -> None:
        """Test mu-law with maximum values."""
        pcm16 = np.array([32767, -32768], dtype=np.int16)
        mulaw = G711Codec.pcm_to_mulaw(pcm16)
        decoded = G711Codec.mulaw_to_pcm(mulaw)
        assert decoded[0] > 30000
        assert decoded[1] < -30000
