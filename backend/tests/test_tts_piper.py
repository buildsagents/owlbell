"""
Tests for Piper TTS service.

Covers synthesis, streaming, sentence buffering, voice selection,
speed control, audio format conversion, and error handling.
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator, List
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.ai.tts.piper_service import (
    G711Codec,
    PiperService,
    PiperServiceError,
    SentenceBuffer,
    TTSConfig,
    TTSRequest,
    TTSResult,
)


# ---------------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def piper_service() -> PiperService:
    """Create a PiperService for testing."""
    return PiperService(
        base_url="http://localhost:9998",
        timeout=5.0,
        max_retries=2,
    )


@pytest.fixture
def sample_pcm16() -> np.ndarray:
    """Generate sample PCM16 audio."""
    t = np.linspace(0, 0.1, int(22050 * 0.1))
    sine = np.sin(2 * np.pi * 440 * t) * 0.5
    return (sine * 32767).astype(np.int16)


# ---------------------------------------------------------------------------
#  TTSConfig tests
# ---------------------------------------------------------------------------


class TestTTSConfig:
    """Tests for TTSConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        assert TTSConfig.DEFAULT_VOICE == "lessac-medium"
        assert TTSConfig.DEFAULT_SPEED == 1.0
        assert TTSConfig.DEFAULT_SAMPLE_RATE == 22050
        assert TTSConfig.TELEPHONY_SAMPLE_RATE == 8000

    def test_speed_map(self) -> None:
        """Test speed mapping."""
        assert "normal" in TTSConfig.SPEED_MAP
        assert "fast" in TTSConfig.SPEED_MAP
        assert "slow" in TTSConfig.SPEED_MAP
        assert TTSConfig.SPEED_MAP["normal"] == 1.0


# ---------------------------------------------------------------------------
#  TTSRequest tests
# ---------------------------------------------------------------------------


class TestTTSRequest:
    """Tests for TTSRequest dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a request."""
        req = TTSRequest(text="Hello world")
        assert req.text == "Hello world"
        assert req.voice == "lessac-medium"
        assert req.speed == 1.0

    def test_to_dict(self) -> None:
        """Test conversion to dict."""
        req = TTSRequest(text="Hello", voice="amy-medium", speed=1.2)
        d = req.to_dict()
        assert d["text"] == "Hello"
        assert d["voice"] == "amy-medium"
        assert d["speed"] == 1.2

    def test_max_length_enforced(self) -> None:
        """Test that text is truncated to max length."""
        long_text = "x" * 3000
        req = TTSRequest(text=long_text)
        d = req.to_dict()
        assert len(d["text"]) <= 2000


# ---------------------------------------------------------------------------
#  TTSResult tests
# ---------------------------------------------------------------------------


class TestTTSResult:
    """Tests for TTSResult dataclass."""

    def test_basic_creation(self, sample_pcm16: np.ndarray) -> None:
        """Test creating a result."""
        wav = PiperService.create_wav_bytes(sample_pcm16)
        result = TTSResult(
            audio=wav,
            pcm16=sample_pcm16,
            sample_rate=22050,
            duration_ms=100,
            text="Hello",
            voice="lessac-medium",
            processing_time_ms=50,
        )
        assert result.text == "Hello"
        assert result.duration_ms == 100
        assert result.duration_sec == 0.1

    def test_mulaw_conversion(self, sample_pcm16: np.ndarray) -> None:
        """Test mu-law property."""
        wav = PiperService.create_wav_bytes(sample_pcm16)
        result = TTSResult(
            audio=wav,
            pcm16=sample_pcm16,
            sample_rate=22050,
            duration_ms=100,
            text="Hello",
            voice="lessac-medium",
            processing_time_ms=50,
        )
        mulaw = result.mulaw_bytes
        assert isinstance(mulaw, bytes)
        assert len(mulaw) == len(sample_pcm16)

    def test_alaw_conversion(self, sample_pcm16: np.ndarray) -> None:
        """Test A-law property."""
        wav = PiperService.create_wav_bytes(sample_pcm16)
        result = TTSResult(
            audio=wav,
            pcm16=sample_pcm16,
            sample_rate=22050,
            duration_ms=100,
            text="Hello",
            voice="lessac-medium",
            processing_time_ms=50,
        )
        alaw = result.alaw_bytes
        assert isinstance(alaw, bytes)
        assert len(alaw) == len(sample_pcm16)


# ---------------------------------------------------------------------------
#  SentenceBuffer tests
# ---------------------------------------------------------------------------


class TestSentenceBuffer:
    """Tests for SentenceBuffer."""

    @pytest.fixture
    def buffer(self) -> SentenceBuffer:
        return SentenceBuffer()

    def test_basic_sentence_detection(self, buffer: SentenceBuffer) -> None:
        """Test basic sentence detection."""
        sentences = buffer.append("Hello world. ")
        assert len(sentences) == 1
        assert sentences[0] == "Hello world"

    def test_multiple_sentences(self, buffer: SentenceBuffer) -> None:
        """Test detecting multiple sentences in one append."""
        sentences = buffer.append("First sentence. Second sentence. ")
        assert len(sentences) == 2
        assert sentences[0] == "First sentence"
        assert sentences[1] == "Second sentence"

    def test_incomplete_sentence(self, buffer: SentenceBuffer) -> None:
        """Test that incomplete sentences stay in buffer."""
        sentences = buffer.append("This is incomplete")
        assert len(sentences) == 0
        assert buffer.buffer_length > 0

    def test_finalize(self, buffer: SentenceBuffer) -> None:
        """Test finalizing buffer."""
        buffer.append("Incomplete sentence")
        sentences = buffer.finalize()
        # Should emit remaining buffer
        assert len(sentences) >= 1
        assert "Incomplete sentence" in sentences[-1]

    def test_reset(self, buffer: SentenceBuffer) -> None:
        """Test buffer reset."""
        buffer.append("Some text. ")
        buffer.reset()
        assert buffer.is_empty
        assert buffer.buffer_length == 0

    def test_is_empty(self, buffer: SentenceBuffer) -> None:
        """Test empty check."""
        assert buffer.is_empty
        buffer.append("Incomplete")
        assert not buffer.is_empty

    def test_abbreviation_handling(self, buffer: SentenceBuffer) -> None:
        """Test that abbreviations don't split sentences."""
        sentences = buffer.append("See Dr. Smith at 3 p.m. today. ")
        # "Dr." and "p.m." should not create false sentence boundaries
        assert all("Dr" not in s or "Smith" in s for s in sentences)

    def test_decimal_number_handling(self, buffer: SentenceBuffer) -> None:
        """Test decimal numbers don't split."""
        sentences = buffer.append("The price is 3.14 dollars. ")
        assert len(sentences) == 1
        assert "3.14" in sentences[0]

    def test_max_buffer_forced_emit(self, buffer: SentenceBuffer) -> None:
        """Test forced emit when buffer exceeds max length."""
        long_text = "x" * 600 + ". "  # Exceeds 500 char max
        sentences = buffer.append(long_text)
        # Should force emit the overflow
        assert len(sentences) >= 1

    def test_exclamation_mark(self, buffer: SentenceBuffer) -> None:
        """Test exclamation mark as sentence ending."""
        sentences = buffer.append("Hello there! How are you? ")
        assert len(sentences) == 2

    def test_question_mark(self, buffer: SentenceBuffer) -> None:
        """Test question mark as sentence ending."""
        sentences = buffer.append("How are you? I'm fine. ")
        assert len(sentences) == 2
        assert "How are you" in sentences[0]


# ---------------------------------------------------------------------------
#  PiperService tests
# ---------------------------------------------------------------------------


class TestPiperService:
    """Tests for PiperService."""

    @pytest.mark.asyncio
    async def test_start_stop(self, piper_service: PiperService) -> None:
        """Test service start and stop."""
        with patch.object(
            piper_service, "health_check", new_callable=AsyncMock
        ) as mock_health:
            mock_health.return_value = True
            await piper_service.start()
            assert piper_service._session is not None

            await piper_service.stop()
            # Session closed check

    @pytest.mark.asyncio
    async def test_health_check_success(self, piper_service: PiperService) -> None:
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status = 200

        mock_session = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.get.return_value = mock_cm

        piper_service._session = mock_session

        result = await piper_service.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, piper_service: PiperService) -> None:
        """Test failed health check."""
        mock_session = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.get.return_value = mock_cm

        piper_service._session = mock_session

        result = await piper_service.health_check()
        assert result is False

    def test_extract_pcm_from_wav(self, sample_pcm16: np.ndarray) -> None:
        """Test PCM extraction from WAV."""
        wav_bytes = PiperService.create_wav_bytes(sample_pcm16, 22050)
        extracted = PiperService._extract_pcm_from_wav(wav_bytes)
        assert len(extracted) == len(sample_pcm16)
        assert extracted.dtype == np.int16

    def test_resample_to_telephony(self, sample_pcm16: np.ndarray) -> None:
        """Test resampling to 8kHz."""
        # Create 1 second at 22kHz
        pcm = np.zeros(22050, dtype=np.int16)
        resampled = PiperService.resample_to_telephony(pcm, source_sr=22050)
        assert len(resampled) == 8000  # 1 second at 8kHz
        assert resampled.dtype == np.int16

    def test_resample_same_rate(self) -> None:
        """Test resampling when source == target."""
        pcm = np.zeros(8000, dtype=np.int16)
        result = PiperService.resample_to_telephony(pcm, source_sr=8000)
        assert result is pcm  # Should return same array

    def test_resample_audio(self) -> None:
        """Test general audio resampling."""
        pcm = np.zeros(16000, dtype=np.int16)
        result = PiperService.resample_audio(pcm, 16000, 8000)
        assert len(result) == 8000
        assert result.dtype == np.int16

    def test_resample_audio_same_rate(self) -> None:
        """Test resampling with same rates."""
        pcm = np.zeros(1000, dtype=np.int16)
        result = PiperService.resample_audio(pcm, 16000, 16000)
        assert result is pcm

    def test_apply_speed(self) -> None:
        """Test speed change."""
        pcm = np.zeros(22050, dtype=np.int16)
        # Fill with pattern
        pcm[:] = np.arange(len(pcm)) % 32767
        faster = PiperService.apply_speed(pcm, 22050, 2.0)
        assert len(faster) == len(pcm) // 2  # Half the duration

    def test_apply_speed_no_change(self) -> None:
        """Test speed=1.0 returns same data."""
        pcm = np.zeros(1000, dtype=np.int16)
        result = PiperService.apply_speed(pcm, 22050, 1.0)
        assert result is pcm

    def test_estimate_duration(self) -> None:
        """Test duration estimation."""
        ms = PiperService.estimate_duration("hello world", speed=1.0)
        assert ms > 0
        # ~150 WPM = ~400ms per word, 2 words = ~800ms
        assert 400 <= ms <= 2000

    def test_estimate_duration_faster(self) -> None:
        """Test duration estimation with faster speed."""
        normal = PiperService.estimate_duration("hello world", speed=1.0)
        fast = PiperService.estimate_duration("hello world", speed=2.0)
        assert fast < normal

    def test_create_wav_bytes(self, sample_pcm16: np.ndarray) -> None:
        """Test WAV file creation."""
        wav = PiperService.create_wav_bytes(sample_pcm16, 22050)
        assert isinstance(wav, bytes)
        assert len(wav) > 44  # WAV header
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"

    def test_select_voice_default(self, piper_service: PiperService) -> None:
        """Test default voice selection."""
        voice = piper_service.select_voice_for_tenant(None)
        assert voice == piper_service.default_voice

    def test_select_voice_from_config(self, piper_service: PiperService) -> None:
        """Test voice selection from tenant config."""
        config = {"voice_id": "amy-medium"}
        voice = piper_service.select_voice_for_tenant(config)
        assert voice == "amy-medium"

    def test_select_voice_quality(self, piper_service: PiperService) -> None:
        """Test voice selection by quality preference."""
        config = {"voice_quality": "low"}
        voice = piper_service.select_voice_for_tenant(config)
        assert voice == "lessac-low"

    @pytest.mark.asyncio
    async def test_synthesize_error_handling(
        self, piper_service: PiperService
    ) -> None:
        """Test synthesis error handling."""
        piper_service._is_healthy = True

        with patch.object(
            piper_service, "_get_session", new_callable=AsyncMock
        ) as mock_session:
            mock_resp = MagicMock()
            mock_resp.status = 500
            mock_resp.text = AsyncMock(return_value="Server error")
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_cm.__aexit__ = AsyncMock(return_value=None)

            mock_sess = MagicMock()
            mock_sess.post.return_value = mock_cm
            mock_session.return_value = mock_sess

            with pytest.raises(PiperServiceError):
                await piper_service.synthesize("Hello")

    @pytest.mark.asyncio
    async def test_synthesize_sentences(self, piper_service: PiperService) -> None:
        """Test sentence-by-sentence synthesis."""
        piper_service._is_healthy = True

        with patch.object(
            piper_service, "synthesize", new_callable=AsyncMock
        ) as mock_synth:
            mock_synth.return_value = MagicMock(
                pcm16=np.zeros(100, dtype=np.int16),
                duration_ms=100,
            )
            results = []
            async for result in piper_service.synthesize_sentences(
                "Hello. How are you? Good!"
            ):
                results.append(result)

            assert len(results) == 3


# ---------------------------------------------------------------------------
#  G.711 Codec tests
# ---------------------------------------------------------------------------


class TestG711Codec:
    """Tests for G.711 codec."""

    def test_pcm_mulaw_roundtrip(self) -> None:
        """Test PCM -> mu-law -> PCM roundtrip."""
        pcm16 = np.array([0, 1000, -1000, 5000, -5000], dtype=np.int16)
        mulaw = G711Codec.pcm_to_mulaw(pcm16)
        pcm_decoded = G711Codec.mulaw_to_pcm(mulaw)
        assert len(pcm_decoded) == len(pcm16)

    def test_mulaw_size(self) -> None:
        """Test mu-law output size."""
        pcm16 = np.zeros(100, dtype=np.int16)
        mulaw = G711Codec.pcm_to_mulaw(pcm16)
        assert len(mulaw) == 100  # 1:1 ratio (16-bit -> 8-bit)

    def test_alaw_output(self) -> None:
        """Test A-law output."""
        pcm16 = np.array([0, 1000, -1000], dtype=np.int16)
        alaw = G711Codec.pcm_to_alaw(pcm16)
        assert isinstance(alaw, bytes)
        assert len(alaw) == 3

    def test_mulaw_silence(self) -> None:
        """Test silence encoding."""
        pcm16 = np.zeros(50, dtype=np.int16)
        mulaw = G711Codec.pcm_to_mulaw(pcm16)
        decoded = G711Codec.mulaw_to_pcm(mulaw)
        assert np.all(np.abs(decoded) < 100)


# ---------------------------------------------------------------------------
#  Streaming tests
# ---------------------------------------------------------------------------


class TestStreaming:
    """Tests for TTS streaming."""

    @pytest.mark.asyncio
    async def test_synthesize_stream(self, piper_service: PiperService) -> None:
        """Test streaming synthesis."""
        piper_service._is_healthy = True

        async def text_gen() -> AsyncGenerator[str, None]:
            yield "Hello. "
            yield "How are you? "

        with patch.object(
            piper_service, "synthesize", new_callable=AsyncMock
        ) as mock_synth:
            mock_synth.return_value = MagicMock(
                pcm16=np.zeros(100, dtype=np.int16),
                duration_ms=100,
            )
            results = []
            async for result in piper_service.synthesize_stream(text_gen()):
                results.append(result)

            assert len(results) == 2
