"""
whisper.cpp HTTP client for speech-to-text.

Handles audio transcription via the whisper.cpp server REST API.
Supports both single-file transcription and streaming chunk transcription.
Includes VAD integration for voice activity detection and confidence scoring.

Usage:
    service = WhisperService()
    result = await service.transcribe(audio_bytes)
    print(result.text, result.confidence)

    # Streaming
    async for partial in service.transcribe_streaming(audio_generator):
        print(f"Partial: {partial.text}")
"""

from __future__ import annotations

import asyncio
import io
import logging
import struct
import time
import wave
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Union,
)
from urllib.parse import urljoin

import aiohttp
import numpy as np

logger = logging.getLogger(__name__)


class ModelSize(str, Enum):
    """Whisper model size options."""

    TINY = "tiny"
    TINY_EN = "tiny.en"
    BASE = "base"
    BASE_EN = "base.en"
    SMALL = "small"
    SMALL_EN = "small.en"
    MEDIUM = "medium"
    MEDIUM_EN = "medium.en"
    LARGE = "large"


@dataclass
class STTResult:
    """Result from whisper.cpp transcription.

    Attributes:
        text: Transcribed text.
        confidence: Confidence score 0.0-1.0.
        language: Detected language code.
        segments: Raw segment data from whisper.cpp.
        processing_time_ms: Time taken to transcribe in milliseconds.
        is_partial: Whether this is a partial (interim) result.
        sequence: Sequence number for streaming results.
    """

    text: str
    confidence: float = 0.0
    language: str = "en"
    segments: List[Dict[str, Any]] = field(default_factory=list)
    processing_time_ms: int = 0
    is_partial: bool = False
    sequence: int = 0

    @property
    def is_empty(self) -> bool:
        """Check if transcription is empty or just whitespace."""
        return not self.text or not self.text.strip()

    @property
    def word_count(self) -> int:
        """Count words in transcription."""
        return len(self.text.split()) if self.text else 0


@dataclass
class VADSegment:
    """Voice activity detection segment.

    Attributes:
        speech: Detected speech audio data (PCM16 bytes).
        start_sample: Start sample index.
        end_sample: End sample index.
        confidence: VAD confidence score.
    """

    speech: bytes
    start_sample: int = 0
    end_sample: int = 0
    confidence: float = 0.0


class WhisperServiceError(Exception):
    """Base exception for Whisper service errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.recoverable = recoverable


class WhisperServiceUnavailable(WhisperServiceError):
    """whisper.cpp server is not reachable."""

    pass


class WhisperTranscriptionError(WhisperServiceError):
    """Error during transcription processing."""

    pass


class VADEngine:
    """Simple energy-based Voice Activity Detection.

    Provides a lightweight VAD fallback when silero-vad is not available.
    Uses frame energy thresholding with hangover logic.

    Attributes:
        threshold: Energy threshold for speech detection (0.0-1.0).
        min_silence_ms: Minimum silence duration to trigger speech end.
        min_speech_ms: Minimum speech duration to be considered valid.
        sample_rate: Expected sample rate.
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
        self._is_speaking: bool = False
        self._speech_buffer: bytearray = bytearray()
        self._silence_duration_ms: float = 0.0
        self._speech_duration_ms: float = 0.0
        self._frame_size: int = int(sample_rate * 0.03 * 2)  # 30ms frames

    def reset(self) -> None:
        """Reset VAD state."""
        self._is_speaking = False
        self._speech_buffer = bytearray()
        self._silence_duration_ms = 0.0
        self._speech_duration_ms = 0.0

    def process(self, pcm16_bytes: bytes) -> Optional[VADSegment]:
        """Process audio chunk and detect speech segments.

        Args:
            pcm16_bytes: 16-bit PCM audio data.

        Returns:
            VADSegment when speech ends, None otherwise.
        """
        self._speech_buffer.extend(pcm16_bytes)
        pcm = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        frame_energy = np.sqrt(np.mean(pcm**2)) if len(pcm) > 0 else 0.0
        frame_duration_ms = (len(pcm) / self.sample_rate) * 1000.0

        if frame_energy > self.threshold:
            self._is_speaking = True
            self._silence_duration_ms = 0.0
            self._speech_duration_ms += frame_duration_ms
        else:
            if self._is_speaking:
                self._silence_duration_ms += frame_duration_ms
                if self._silence_duration_ms >= self.min_silence_ms:
                    if self._speech_duration_ms >= self.min_speech_ms:
                        segment = VADSegment(
                            speech=bytes(self._speech_buffer),
                            confidence=min(1.0, frame_energy / self.threshold),
                        )
                        self.reset()
                        return segment
                    self.reset()
            else:
                # Discard non-speech audio
                self._speech_buffer = bytearray()
        return None


class WhisperService:
    """Client for whisper.cpp HTTP server.

    Handles streaming transcription from audio chunks via WebSocket
    or HTTP, VAD integration, language detection, and confidence scoring.

    Args:
        base_url: URL of the whisper.cpp server.
        timeout: HTTP request timeout in seconds.
        max_retries: Max retry attempts for failed requests.
        retry_delay: Delay between retries in seconds.
        model: Model size to use for transcription.
        vad_threshold: VAD energy threshold.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8081",
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        model: ModelSize = ModelSize.BASE_EN,
        vad_threshold: float = 0.02,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.model = model
        self._session: Optional[aiohttp.ClientSession] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_healthy: bool = False
        self._vad = VADEngine(threshold=vad_threshold)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session (connection pool)."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"Content-Type": "audio/wav"},
            )
        return self._session

    async def start(self) -> None:
        """Start the service: create session, begin health checks."""
        await self._get_session()
        await self.health_check()
        self._health_check_task = asyncio.create_task(
            self._health_check_loop(), name="whisper_health_check"
        )
        logger.info(
            f"WhisperService started (model={self.model.value}, "
            f"health={self._is_healthy})"
        )

    async def stop(self) -> None:
        """Stop the service and cleanup resources."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        logger.info("WhisperService stopped")

    async def _health_check_loop(self) -> None:
        """Background task to check whisper.cpp health every 30s."""
        while True:
            try:
                await asyncio.sleep(30)
                await self.health_check()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"Health check error: {exc}")
                self._is_healthy = False

    async def health_check(self) -> bool:
        """Check if whisper.cpp server is healthy.

        Returns:
            True if server is responding to health endpoint.
        """
        try:
            session = await self._get_session()
            async with session.get(
                urljoin(self.base_url, "/health"),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                self._is_healthy = resp.status == 200
                if self._is_healthy:
                    logger.debug("whisper.cpp health check: OK")
                return self._is_healthy
        except Exception as exc:
            logger.warning(f"whisper.cpp health check failed: {exc}")
            self._is_healthy = False
            return False

    @property
    def is_healthy(self) -> bool:
        """Return cached health status."""
        return self._is_healthy

    @staticmethod
    def _prepare_wav(
        audio_data: Union[bytes, np.ndarray],
        sample_rate: int = 16000,
    ) -> bytes:
        """Convert raw audio bytes or numpy array to WAV format.

        Args:
            audio_data: Raw PCM16 audio or numpy array.
            sample_rate: Audio sample rate (default 16000 for whisper).

        Returns:
            WAV file bytes.
        """
        if isinstance(audio_data, np.ndarray):
            if audio_data.dtype != np.int16:
                audio_data = (audio_data * 32767).astype(np.int16)
            audio_bytes = audio_data.tobytes()
        else:
            audio_bytes = audio_data

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav:
            wav.setnchannels(1)  # Mono
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            wav.writeframes(audio_bytes)
        return wav_buffer.getvalue()

    @staticmethod
    def _resample_8k_to_16k(pcm8k: np.ndarray) -> np.ndarray:
        """Resample 8kHz audio to 16kHz using linear interpolation.

        Args:
            pcm8k: 16-bit PCM audio at 8000Hz.

        Returns:
            Resampled audio at 16000Hz.
        """
        ratio = 2.0  # 16000 / 8000
        new_length = int(len(pcm8k) * ratio)
        old_indices = np.arange(len(pcm8k))
        new_indices = np.linspace(0, len(pcm8k) - 1, new_length)
        return np.interp(new_indices, old_indices, pcm8k).astype(np.int16)

    async def transcribe(
        self,
        audio_data: Union[bytes, np.ndarray],
        sample_rate: int = 16000,
        language: str = "en",
    ) -> STTResult:
        """Transcribe audio to text.

        Args:
            audio_data: Raw PCM16 audio bytes or numpy array.
            sample_rate: Sample rate of audio (default 16000).
            language: Language code (default "en").

        Returns:
            STTResult with text and metadata.

        Raises:
            WhisperServiceUnavailable: If server is not reachable.
            WhisperTranscriptionError: If transcription fails.
        """
        if not self._is_healthy:
            if not await self.health_check():
                raise WhisperServiceUnavailable(
                    "whisper.cpp server is not healthy",
                    recoverable=True,
                )

        start_time = time.perf_counter()

        # Convert to WAV
        wav_data = self._prepare_wav(audio_data, sample_rate)

        # Build request parameters
        params = {
            "language": language,
            "temperature": "0.0",
            "response_format": "json",
        }

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                session = await self._get_session()

                async with session.post(
                    urljoin(self.base_url, "/inference"),
                    data=wav_data,
                    params=params,
                    headers={"Content-Type": "audio/wav"},
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()

                        processing_time = int(
                            (time.perf_counter() - start_time) * 1000
                        )

                        # Parse response
                        text = result.get("text", "").strip()
                        segments = result.get("segments", [])

                        # Calculate confidence from segment-level probabilities
                        confidence = self._calculate_confidence(segments)

                        # Detect language if returned
                        detected_lang = result.get("language", language)

                        return STTResult(
                            text=text,
                            confidence=confidence,
                            language=detected_lang,
                            segments=segments,
                            processing_time_ms=processing_time,
                            is_partial=False,
                        )

                    elif resp.status == 429:  # Rate limited
                        retry_after = float(
                            resp.headers.get("Retry-After", self.retry_delay)
                        )
                        logger.warning(
                            f"Rate limited, waiting {retry_after}s (attempt {attempt})"
                        )
                        await asyncio.sleep(retry_after)
                        last_error = WhisperTranscriptionError(
                            f"Rate limited (attempt {attempt})",
                            status_code=429,
                        )

                    elif resp.status >= 500:  # Server error, retry
                        logger.warning(
                            f"Server error {resp.status} "
                            f"(attempt {attempt}/{self.max_retries})"
                        )
                        if attempt < self.max_retries:
                            await asyncio.sleep(self.retry_delay * attempt)
                        last_error = WhisperTranscriptionError(
                            f"Server error: {resp.status}",
                            status_code=resp.status,
                            recoverable=True,
                        )

                    else:  # Client error, don't retry
                        body = await resp.text()
                        raise WhisperTranscriptionError(
                            f"Client error {resp.status}: {body}",
                            status_code=resp.status,
                            recoverable=False,
                        )

            except asyncio.TimeoutError:
                logger.warning(f"Timeout (attempt {attempt}/{self.max_retries})")
                last_error = WhisperServiceUnavailable(
                    f"Request timeout (attempt {attempt})",
                    recoverable=True,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)

            except aiohttp.ClientError as exc:
                logger.warning(f"Connection error: {exc} (attempt {attempt})")
                self._is_healthy = False
                last_error = WhisperServiceUnavailable(
                    f"Connection error: {exc}",
                    recoverable=True,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)

        # All retries exhausted
        raise last_error or WhisperTranscriptionError("All retry attempts failed")

    async def transcribe_8khz(
        self,
        audio_data: Union[bytes, np.ndarray],
        language: str = "en",
    ) -> STTResult:
        """Transcribe 8kHz audio (telephony format).

        Automatically resamples from 8kHz to 16kHz before transcription.

        Args:
            audio_data: Raw PCM16 audio at 8000Hz.
            language: Language code.

        Returns:
            STTResult with transcribed text.
        """
        if isinstance(audio_data, bytes):
            pcm8k = np.frombuffer(audio_data, dtype=np.int16)
        else:
            pcm8k = audio_data.astype(np.int16)
        pcm16k = self._resample_8k_to_16k(pcm8k)
        return await self.transcribe(pcm16k, sample_rate=16000, language=language)

    async def transcribe_streaming(
        self,
        audio_generator: AsyncGenerator[bytes, None],
        sample_rate: int = 16000,
        language: str = "en",
        chunk_duration_ms: int = 1000,
    ) -> AsyncGenerator[STTResult, None]:
        """Streaming transcription from an async audio generator.

        Accumulates audio chunks and transcribes at specified intervals.
        Yields partial results for real-time display.

        Args:
            audio_generator: Async generator yielding PCM16 audio chunks.
            sample_rate: Audio sample rate.
            language: Language code.
            chunk_duration_ms: How often to transcribe (default 1000ms).

        Yields:
            STTResult (is_partial=True for interim results).
        """
        buffer = bytearray()
        bytes_per_chunk = int(sample_rate * 2 * chunk_duration_ms / 1000)
        sequence = 0

        async for chunk in audio_generator:
            buffer.extend(chunk)

            # Transcribe when we have enough data
            while len(buffer) >= bytes_per_chunk:
                chunk_data = bytes(buffer[:bytes_per_chunk])
                buffer = buffer[bytes_per_chunk:]

                try:
                    result = await self.transcribe(chunk_data, sample_rate, language)
                    result.is_partial = True
                    result.sequence = sequence
                    sequence += 1
                    yield result
                except Exception as exc:
                    logger.error(f"Streaming transcription error: {exc}")

        # Final transcription of remaining buffer
        if len(buffer) > sample_rate * 2 * 0.5:  # At least 500ms
            try:
                result = await self.transcribe(bytes(buffer), sample_rate, language)
                result.is_partial = False
                result.sequence = sequence
                yield result
            except Exception as exc:
                logger.error(f"Final transcription error: {exc}")

    async def transcribe_with_vad(
        self,
        audio_generator: AsyncGenerator[bytes, None],
        sample_rate: int = 16000,
        language: str = "en",
    ) -> AsyncGenerator[STTResult, None]:
        """Transcribe with integrated VAD for speech-end detection.

        Uses the built-in VAD engine to detect speech segments and
        only sends detected speech to whisper.cpp.

        Args:
            audio_generator: Async generator of PCM16 audio chunks.
            sample_rate: Audio sample rate.
            language: Language code.

        Yields:
            STTResult for each detected speech segment.
        """
        self._vad.reset()
        self._vad.sample_rate = sample_rate
        self._vad._frame_size = int(sample_rate * 0.03 * 2)

        async for chunk in audio_generator:
            segment = self._vad.process(chunk)
            if segment is not None:
                try:
                    result = await self.transcribe(
                        segment.speech, sample_rate, language
                    )
                    result.is_partial = False
                    yield result
                except Exception as exc:
                    logger.error(f"VAD transcription error: {exc}")

    def _calculate_confidence(self, segments: List[Dict[str, Any]]) -> float:
        """Calculate overall confidence from segment-level data.

        Uses average of segment avg_logprob, clamped to [0, 1].

        Args:
            segments: whisper.cpp segments output.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if not segments:
            return 0.0

        confidences: List[float] = []
        for seg in segments:
            logprob = seg.get("avg_logprob", -1.0)
            # Convert logprob to approximate confidence
            # logprob ranges roughly from -1.0 (good) to -3.0 (poor)
            conf = max(0.0, min(1.0, 1.0 + logprob / 1.5))
            confidences.append(conf)

        return sum(confidences) / len(confidences) if confidences else 0.0

    async def detect_language(
        self,
        audio_data: Union[bytes, np.ndarray],
        sample_rate: int = 16000,
    ) -> str:
        """Detect the language of the audio.

        Args:
            audio_data: Raw PCM16 audio bytes.
            sample_rate: Audio sample rate.

        Returns:
            ISO 639-1 language code (e.g., 'en', 'es', 'fr').
        """
        result = await self.transcribe(audio_data, sample_rate, language="auto")
        return result.language

    # ------------------------------------------------------------------ #
    #  Utility helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def pcm_to_float(pcm16: np.ndarray) -> np.ndarray:
        """Convert int16 PCM to float32 in range [-1, 1].

        Args:
            pcm16: 16-bit PCM audio data.

        Returns:
            Float32 audio data.
        """
        return pcm16.astype(np.float32) / 32768.0

    @staticmethod
    def float_to_pcm(audio_float: np.ndarray) -> np.ndarray:
        """Convert float32 audio to int16 PCM.

        Args:
            audio_float: Float32 audio in range [-1, 1].

        Returns:
            16-bit PCM audio data.
        """
        return (np.clip(audio_float, -1.0, 1.0) * 32767).astype(np.int16)

    @staticmethod
    def apply_gain(pcm16: np.ndarray, gain_db: float) -> np.ndarray:
        """Apply gain to audio in decibels.

        Args:
            pcm16: Input PCM16 audio.
            gain_db: Gain to apply in dB (positive = louder).

        Returns:
            Audio with applied gain, clipped to int16 range.
        """
        gain_linear = 10 ** (gain_db / 20.0)
        float_audio = WhisperService.pcm_to_float(pcm16)
        return WhisperService.float_to_pcm(float_audio * gain_linear)

    @staticmethod
    def normalize_audio(pcm16: np.ndarray, target_db: float = -20.0) -> np.ndarray:
        """Normalize audio to target RMS level.

        Args:
            pcm16: Input PCM16 audio.
            target_db: Target RMS level in dBFS.

        Returns:
            Normalized audio.
        """
        float_audio = WhisperService.pcm_to_float(pcm16)
        rms = np.sqrt(np.mean(float_audio**2))
        if rms < 1e-10:
            return pcm16
        current_db = 20 * np.log10(rms)
        gain_db = target_db - current_db
        return WhisperService.apply_gain(pcm16, gain_db)


# ------------------------------------------------------------------ #
#  Factory functions for dependency injection
# ------------------------------------------------------------------ #

_whisper_service_instance: Optional[WhisperService] = None


async def get_whisper_service() -> WhisperService:
    """Get or create singleton WhisperService instance.

    Returns:
        Configured WhisperService instance.
    """
    global _whisper_service_instance
    if _whisper_service_instance is None:
        _whisper_service_instance = WhisperService(
            base_url="http://localhost:8081",
            timeout=10.0,
            max_retries=3,
            retry_delay=1.0,
            model=ModelSize.BASE_EN,
        )
        await _whisper_service_instance.start()
    return _whisper_service_instance


async def close_whisper_service() -> None:
    """Close the singleton instance."""
    global _whisper_service_instance
    if _whisper_service_instance:
        await _whisper_service_instance.stop()
        _whisper_service_instance = None
