"""
Piper TTS client for text-to-speech synthesis.

Handles sentence-level buffering for streaming TTS, voice selection,
speed control, audio format conversion (WAV to G.711 mu-law), and
audio resampling for telephony.

Usage:
    service = PiperService()
    audio = await service.synthesize("Hello, how can I help you?")
    async for chunk in service.synthesize_stream("Long text here..."):
        play_audio(chunk)
"""

from __future__ import annotations

import asyncio
import base64
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
    Tuple,
)
from urllib.parse import urljoin

import aiohttp
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Audio codec helpers
# ---------------------------------------------------------------------------


class G711Codec:
    """G.711 mu-law (PCMU) audio codec for telephony.

    Converts between 16-bit PCM and 8-bit mu-law compressed audio.
    """

    # Mu-law compression lookup table
    _MU_LAW_ENCODE_TABLE: Optional[np.ndarray] = None
    _MU_LAW_DECODE_TABLE: Optional[np.ndarray] = None

    BIAS = 33
    MAX = 0x1FFF  # Maximum that can be represented

    @classmethod
    def _init_tables(cls) -> None:
        """Initialize encode/decode lookup tables."""
        if cls._MU_LAW_ENCODE_TABLE is not None:
            return

        # Build decode table: 256 mu-law values -> 16-bit PCM
        decode = np.zeros(256, dtype=np.int16)
        for i in range(256):
            mu = ~i & 0xFF  # Bit inversion
            sign = -1 if (mu & 0x80) else 1
            exponent = (mu >> 4) & 0x07
            mantissa = mu & 0x0F
            magnitude = ((mantissa << 1) | 0x21) << (exponent + 2)
            decode[i] = np.int16(sign * (magnitude - cls.BIAS))
        cls._MU_LAW_DECODE_TABLE = decode

        # Build encode table: 16-bit PCM -> mu-law
        encode = np.zeros(65536, dtype=np.uint8)
        for pcm in range(-32768, 32768):
            idx = pcm & 0xFFFF
            # Simple algorithmic encoding
            sign = 0x80 if pcm < 0 else 0
            magnitude = abs(pcm)
            magnitude += cls.BIAS
            if magnitude > cls.MAX:
                magnitude = cls.MAX

            if magnitude >= 0x4000:
                exponent = 6
                mantissa = (magnitude >> 9) & 0x0F
            elif magnitude >= 0x2000:
                exponent = 5
                mantissa = (magnitude >> 8) & 0x0F
            elif magnitude >= 0x1000:
                exponent = 4
                mantissa = (magnitude >> 7) & 0x0F
            elif magnitude >= 0x0800:
                exponent = 3
                mantissa = (magnitude >> 6) & 0x0F
            elif magnitude >= 0x0400:
                exponent = 2
                mantissa = (magnitude >> 5) & 0x0F
            elif magnitude >= 0x0200:
                exponent = 1
                mantissa = (magnitude >> 4) & 0x0F
            elif magnitude >= 0x0100:
                exponent = 0
                mantissa = (magnitude >> 3) & 0x0F
            else:
                exponent = 0
                mantissa = magnitude >> 3

            ulaw = ~(sign | (exponent << 4) | mantissa) & 0xFF
            encode[idx] = np.uint8(ulaw)

        cls._MU_LAW_ENCODE_TABLE = encode

    @classmethod
    def pcm_to_mulaw(cls, pcm16: np.ndarray) -> bytes:
        """Convert 16-bit PCM to G.711 mu-law.

        Args:
            pcm16: 16-bit PCM audio data.

        Returns:
            Mu-law encoded bytes.
        """
        cls._init_tables()
        assert cls._MU_LAW_ENCODE_TABLE is not None
        indices = pcm16.astype(np.int32) & 0xFFFF
        return cls._MU_LAW_ENCODE_TABLE[indices].tobytes()

    @classmethod
    def mulaw_to_pcm(cls, mulaw: bytes) -> np.ndarray:
        """Convert G.711 mu-law to 16-bit PCM.

        Args:
            mulaw: Mu-law encoded bytes.

        Returns:
            16-bit PCM numpy array.
        """
        cls._init_tables()
        assert cls._MU_LAW_DECODE_TABLE is not None
        indices = np.frombuffer(mulaw, dtype=np.uint8)
        return cls._MU_LAW_DECODE_TABLE[indices]

    @classmethod
    def pcm_to_alaw(cls, pcm16: np.ndarray) -> bytes:
        """Convert 16-bit PCM to G.711 A-law.

        Args:
            pcm16: 16-bit PCM audio data.

        Returns:
            A-law encoded bytes.
        """
        # Simplified A-law encoding
        alaw = np.zeros(len(pcm16), dtype=np.uint8)
        for i, sample in enumerate(pcm16):
            sign = 0x80 if sample < 0 else 0
            magnitude = abs(int(sample))

            if magnitude > 32635:
                magnitude = 32635

            if magnitude >= 256:
                exponent = min(7, (magnitude.bit_length() - 1) - 7)
                mantissa = (magnitude >> (exponent + 3)) & 0x0F
                alaw[i] = sign | ((exponent + 1) << 4) | mantissa
            else:
                alaw[i] = sign | (magnitude >> 4)

            # Even bit inversion for A-law
            alaw[i] ^= 0xD5

        return alaw.tobytes()


# ---------------------------------------------------------------------------
#  Data models
# ---------------------------------------------------------------------------


@dataclass
class TTSConfig:
    """Configuration for TTS synthesis."""

    DEFAULT_VOICE = "lessac-medium"
    FAST_VOICE = "lessac-low"
    ALTERNATE_VOICE = "amy-medium"

    DEFAULT_SPEED = 1.0
    DEFAULT_SAMPLE_RATE = 22050
    TELEPHONY_SAMPLE_RATE = 8000

    # Sentence splitting pattern
    SENTENCE_ENDINGS = r"(?<=[.!?])\s+"

    # Speed mapping based on urgency
    SPEED_MAP: Dict[str, float] = field(
        default_factory=lambda: {
            "normal": 1.0,
            "fast": 1.2,
            "slow": 0.85,
        }
    )


@dataclass
class TTSRequest:
    """TTS synthesis request.

    Attributes:
        text: Text to synthesize.
        voice: Voice ID to use.
        speed: Speaking speed multiplier (0.5-2.0).
        output_format: Output audio format (wav or pcm).
        sample_rate: Output sample rate.
    """

    text: str
    voice: str = "lessac-medium"
    speed: float = 1.0
    output_format: str = "wav"
    sample_rate: int = 22050

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API payload dict."""
        return {
            "text": self.text[:2000],
            "voice": self.voice,
            "speed": self.speed,
            "output_format": self.output_format,
            "sample_rate": self.sample_rate,
        }


@dataclass
class TTSResult:
    """Result from TTS synthesis.

    Attributes:
        audio: WAV file bytes.
        pcm16: Raw PCM16 audio array.
        sample_rate: Audio sample rate.
        duration_ms: Audio duration in milliseconds.
        text: Text that was synthesized.
        voice: Voice ID used.
        processing_time_ms: Time taken to synthesize.
    """

    audio: bytes
    pcm16: np.ndarray
    sample_rate: int
    duration_ms: int
    text: str
    voice: str
    processing_time_ms: int

    @property
    def duration_sec(self) -> float:
        """Audio duration in seconds."""
        return self.duration_ms / 1000.0

    @property
    def mulaw_bytes(self) -> bytes:
        """Get G.711 mu-law encoded audio."""
        return G711Codec.pcm_to_mulaw(self.pcm16)

    @property
    def alaw_bytes(self) -> bytes:
        """Get G.711 A-law encoded audio."""
        return G711Codec.pcm_to_alaw(self.pcm16)


# ---------------------------------------------------------------------------
#  Sentence buffer for streaming
# ---------------------------------------------------------------------------


class SentenceBuffer:
    """Buffers streaming text and emits complete sentences.

    Uses punctuation-based sentence splitting with special handling
    for abbreviations, numbers, and phone numbers.

    Args:
        min_sentence_length: Minimum chars to consider a sentence.
        max_buffer_length: Maximum buffer size before forced emit.
    """

    ABBREVIATIONS = {
        "mr.",
        "mrs.",
        "ms.",
        "dr.",
        "prof.",
        "st.",
        "ave.",
        "blvd.",
        "rd.",
        "a.m.",
        "p.m.",
        "e.g.",
        "i.e.",
        "jan.",
        "feb.",
        "mar.",
        "apr.",
        "jun.",
        "jul.",
        "aug.",
        "sep.",
        "oct.",
        "nov.",
        "dec.",
        "mon.",
        "tue.",
        "wed.",
        "thu.",
        "fri.",
        "sat.",
        "sun.",
        "no.",
        "vol.",
        "inc.",
        "ltd.",
        "llc.",
    }

    def __init__(
        self,
        min_sentence_length: int = 10,
        max_buffer_length: int = 500,
    ) -> None:
        self.min_sentence_length = min_sentence_length
        self.max_buffer_length = max_buffer_length
        self._buffer: str = ""
        self._sequence: int = 0
        self._is_complete: bool = False

    def append(self, token: str) -> List[str]:
        """Append a token to the buffer and return complete sentences.

        Args:
            token: New text token from LLM stream.

        Returns:
            List of completed sentence strings.
        """
        self._buffer += token
        return self._flush_sentences()

    def finalize(self) -> List[str]:
        """Force emit remaining buffer content.

        Call when LLM stream is complete.

        Returns:
            List of remaining sentences.
        """
        self._is_complete = True
        sentences = self._flush_sentences()

        remaining = self._buffer.strip()
        if remaining:
            sentences.append(remaining)
            self._sequence += 1
            self._buffer = ""

        return sentences

    def _flush_sentences(self) -> List[str]:
        """Extract complete sentences from buffer."""
        sentences: List[str] = []

        while len(self._buffer) >= self.min_sentence_length:
            boundary = self._find_sentence_boundary()
            if boundary is None:
                break

            sentence_text = self._buffer[:boundary].strip()
            self._buffer = self._buffer[boundary:].lstrip()

            if sentence_text:
                sentences.append(sentence_text)
                self._sequence += 1

        # Force emit if buffer is too long
        if len(self._buffer) >= self.max_buffer_length:
            forced = self._buffer.strip()
            if forced:
                sentences.append(forced)
                self._sequence += 1
            self._buffer = ""

        return sentences

    def _find_sentence_boundary(self) -> Optional[int]:
        """Find the index of the next valid sentence boundary.

        Handles abbreviations and special cases.

        Returns:
            Index after sentence boundary, or None.
        """
        buffer_lower = self._buffer.lower()

        for i, char in enumerate(self._buffer):
            if char not in ".!?" or i < self.min_sentence_length:
                continue

            # Check if part of an abbreviation
            word_start = i
            while word_start > 0 and self._buffer[word_start - 1].isalnum():
                word_start -= 1

            word = buffer_lower[word_start : i + 1]
            if word in self.ABBREVIATIONS:
                continue

            # Check for decimal numbers
            if (
                i > 0
                and self._buffer[i - 1].isdigit()
                and i + 1 < len(self._buffer)
                and self._buffer[i + 1].isdigit()
            ):
                continue

            # Valid sentence boundary found
            end = i + 1
            while end < len(self._buffer) and self._buffer[end].isspace():
                end += 1

            return end

        return None

    def reset(self) -> None:
        """Clear the buffer."""
        self._buffer = ""
        self._sequence = 0
        self._is_complete = False

    @property
    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return not self._buffer.strip()

    @property
    def buffer_length(self) -> int:
        """Current buffer length."""
        return len(self._buffer)


# ---------------------------------------------------------------------------
#  Piper service
# ---------------------------------------------------------------------------


class PiperServiceError(Exception):
    """Base TTS service error."""

    def __init__(self, message: str, recoverable: bool = True):
        super().__init__(message)
        self.recoverable = recoverable


class PiperService:
    """Client for Piper TTS HTTP server.

    Features:
    - Single-text and streaming synthesis.
    - Sentence buffering for parallel TTS+LLM.
    - Voice selection per tenant and speed control.
    - Automatic audio resampling to telephony rates.
    - G.711 mu-law and A-law conversion.
    - Connection pooling and health checks.

    Args:
        base_url: Piper server URL.
        default_voice: Default voice ID.
        timeout: Request timeout.
        max_retries: Max retries.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8082",
        default_voice: str = TTSConfig.DEFAULT_VOICE,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_voice = default_voice
        self.timeout = timeout
        self.max_retries = max_retries

        self._session: Optional[aiohttp.ClientSession] = None
        self._is_healthy: bool = False
        self._voice_cache: Dict[str, Dict[str, Any]] = {}
        self._sentence_buffer = SentenceBuffer()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._session

    async def start(self) -> None:
        """Start the service."""
        await self._get_session()
        await self.health_check()
        logger.info(f"PiperService started, health={self._is_healthy}")

    async def stop(self) -> None:
        """Stop the service."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        logger.info("PiperService stopped")

    async def health_check(self) -> bool:
        """Check Piper server health."""
        try:
            session = await self._get_session()
            async with session.get(
                urljoin(self.base_url, "/health"),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                self._is_healthy = resp.status == 200
                return self._is_healthy
        except Exception as exc:
            logger.warning(f"Piper health check failed: {exc}")
            self._is_healthy = False
            return False

    @property
    def is_healthy(self) -> bool:
        """Return cached health status."""
        return self._is_healthy

    async def list_voices(self) -> List[Dict[str, Any]]:
        """Get list of available voices from the server.

        Returns:
            List of voice info dicts.
        """
        try:
            session = await self._get_session()
            async with session.get(
                urljoin(self.base_url, "/voices"),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    voices = await resp.json()
                    self._voice_cache = {v["id"]: v for v in voices}
                    return voices
                return []
        except Exception as exc:
            logger.warning(f"Failed to list voices: {exc}")
            return []

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = TTSConfig.DEFAULT_SPEED,
        sample_rate: int = TTSConfig.DEFAULT_SAMPLE_RATE,
    ) -> TTSResult:
        """Synthesize text to speech (single request).

        Args:
            text: Text to synthesize (max 2000 chars).
            voice: Voice ID (default: self.default_voice).
            speed: Speed multiplier (0.5-2.0).
            sample_rate: Output sample rate.

        Returns:
            TTSResult with audio data.

        Raises:
            PiperServiceError: If synthesis fails.
        """
        voice = voice or self.default_voice
        start_time = time.perf_counter()

        # Validate voice
        if voice not in ["lessac-medium", "lessac-low", "amy-medium"]:
            voice = self.default_voice

        payload = {
            "text": text[:2000],
            "voice": voice,
            "speed": speed,
            "output_format": "wav",
            "sample_rate": sample_rate,
        }

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                session = await self._get_session()

                async with session.post(
                    urljoin(self.base_url, "/tts"),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()

                        processing_time = int(
                            (time.perf_counter() - start_time) * 1000
                        )

                        # Decode base64 audio
                        wav_bytes = base64.b64decode(result["audio"])
                        pcm16 = self._extract_pcm_from_wav(wav_bytes)

                        return TTSResult(
                            audio=wav_bytes,
                            pcm16=pcm16,
                            sample_rate=result.get("sample_rate", sample_rate),
                            duration_ms=result.get("duration_ms", 0),
                            text=result.get("text", text),
                            voice=result.get("voice", voice),
                            processing_time_ms=processing_time,
                        )

                    elif resp.status >= 500:
                        body = await resp.text()
                        logger.warning(f"Piper server error {resp.status}: {body}")
                        last_error = PiperServiceError(
                            f"Server error {resp.status}", recoverable=True
                        )
                        if attempt < self.max_retries:
                            await asyncio.sleep(0.5 * attempt)

                    else:
                        body = await resp.text()
                        raise PiperServiceError(
                            f"Client error {resp.status}: {body}",
                            recoverable=False,
                        )

            except asyncio.TimeoutError:
                logger.warning(f"TTS timeout (attempt {attempt})")
                last_error = PiperServiceError("Timeout", recoverable=True)
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * attempt)

            except aiohttp.ClientError as exc:
                logger.warning(f"TTS connection error: {exc}")
                self._is_healthy = False
                last_error = PiperServiceError(
                    f"Connection error: {exc}", recoverable=True
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(1.0 * attempt)

        raise last_error or PiperServiceError("All TTS attempts failed")

    async def synthesize_stream(
        self,
        text_stream: AsyncGenerator[str, None],
        voice: Optional[str] = None,
        speed: float = TTSConfig.DEFAULT_SPEED,
        sample_rate: int = TTSConfig.TELEPHONY_SAMPLE_RATE,
    ) -> AsyncGenerator[TTSResult, None]:
        """Streaming TTS from an async text generator.

        Buffers text into sentences and synthesizes each sentence
        as it completes. This allows TTS to begin before the full
        LLM response is received.

        Args:
            text_stream: Async generator yielding text tokens.
            voice: Voice ID.
            speed: Speed multiplier.
            sample_rate: Output sample rate.

        Yields:
            TTSResult for each completed sentence.
        """
        buffer = ""
        sentence_pattern = r"[^.!?]*[.!?]+\s*"
        import re

        pattern = re.compile(sentence_pattern)

        async for token in text_stream:
            buffer += token

            while True:
                match = pattern.match(buffer)
                if not match:
                    break

                sentence = match.group(0)
                buffer = buffer[match.end() :]

                if sentence.strip():
                    try:
                        result = await self.synthesize(
                            sentence.strip(),
                            voice=voice,
                            speed=speed,
                            sample_rate=sample_rate,
                        )
                        yield result
                    except Exception as exc:
                        logger.error(f"Sentence synthesis error: {exc}")

        # Synthesize remaining text
        if buffer.strip():
            try:
                result = await self.synthesize(
                    buffer.strip(),
                    voice=voice,
                    speed=speed,
                    sample_rate=sample_rate,
                )
                yield result
            except Exception as exc:
                logger.error(f"Final synthesis error: {exc}")

    async def synthesize_sentences(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = TTSConfig.DEFAULT_SPEED,
        sample_rate: int = TTSConfig.TELEPHONY_SAMPLE_RATE,
    ) -> AsyncGenerator[TTSResult, None]:
        """Split text into sentences and synthesize each.

        Args:
            text: Full text to synthesize.
            voice: Voice ID.
            speed: Speed multiplier.
            sample_rate: Output sample rate.

        Yields:
            TTSResult per sentence.
        """
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            try:
                result = await self.synthesize(
                    sentence,
                    voice=voice,
                    speed=speed,
                    sample_rate=sample_rate,
                )
                yield result
            except Exception as exc:
                logger.error(f"Sentence synthesis error: {exc}")

    async def synthesize_to_mulaw(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = TTSConfig.DEFAULT_SPEED,
    ) -> Tuple[bytes, int]:
        """Synthesize text to G.711 mu-law for telephony.

        Args:
            text: Text to synthesize.
            voice: Voice ID.
            speed: Speed multiplier.

        Returns:
            Tuple of (mu-law bytes, duration_ms).
        """
        result = await self.synthesize(
            text,
            voice=voice,
            speed=speed,
            sample_rate=TTSConfig.TELEPHONY_SAMPLE_RATE,
        )
        return result.mulaw_bytes, result.duration_ms

    async def synthesize_to_alaw(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: float = TTSConfig.DEFAULT_SPEED,
    ) -> Tuple[bytes, int]:
        """Synthesize text to G.711 A-law for telephony.

        Args:
            text: Text to synthesize.
            voice: Voice ID.
            speed: Speed multiplier.

        Returns:
            Tuple of (A-law bytes, duration_ms).
        """
        result = await self.synthesize(
            text,
            voice=voice,
            speed=speed,
            sample_rate=TTSConfig.TELEPHONY_SAMPLE_RATE,
        )
        return result.alaw_bytes, result.duration_ms

    # ------------------------------------------------------------------ #
    #  Audio utility methods
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_pcm_from_wav(wav_bytes: bytes) -> np.ndarray:
        """Extract PCM16 data from WAV file bytes.

        Args:
            wav_bytes: WAV file bytes.

        Returns:
            16-bit PCM numpy array.
        """
        buffer = io.BytesIO(wav_bytes)
        with wave.open(buffer, "rb") as wav:
            pcm = wav.readframes(wav.getnframes())
            return np.frombuffer(pcm, dtype=np.int16)

    @staticmethod
    def resample_to_telephony(
        pcm16: np.ndarray,
        source_sr: int = 22050,
    ) -> np.ndarray:
        """Resample PCM16 audio to 8kHz for telephony.

        Args:
            pcm16: Source audio at source_sr.
            source_sr: Source sample rate.

        Returns:
            Resampled audio at 8000Hz.
        """
        if source_sr == 8000:
            return pcm16

        ratio = 8000 / source_sr
        new_length = int(len(pcm16) * ratio)

        old_indices = np.arange(len(pcm16))
        new_indices = np.linspace(0, len(pcm16) - 1, new_length)

        return np.interp(new_indices, old_indices, pcm16).astype(np.int16)

    @staticmethod
    def resample_audio(
        pcm16: np.ndarray,
        orig_sr: int,
        target_sr: int,
    ) -> np.ndarray:
        """Resample PCM16 audio using linear interpolation.

        Args:
            pcm16: Source audio.
            orig_sr: Original sample rate.
            target_sr: Target sample rate.

        Returns:
            Resampled audio.
        """
        if orig_sr == target_sr:
            return pcm16

        ratio = target_sr / orig_sr
        new_length = int(len(pcm16) * ratio)

        old_indices = np.arange(len(pcm16))
        new_indices = np.linspace(0, len(pcm16) - 1, new_length)

        return np.interp(new_indices, old_indices, pcm16).astype(np.int16)

    @staticmethod
    def apply_speed(
        pcm16: np.ndarray,
        sample_rate: int,
        speed: float,
    ) -> np.ndarray:
        """Change audio playback speed using linear interpolation.

        Args:
            pcm16: Source audio.
            sample_rate: Audio sample rate.
            speed: Speed multiplier (>1 = faster, <1 = slower).

        Returns:
            Speed-adjusted audio.
        """
        if speed == 1.0:
            return pcm16

        # Time-stretch by resampling
        new_length = int(len(pcm16) / speed)
        old_indices = np.arange(len(pcm16))
        new_indices = np.linspace(0, len(pcm16) - 1, new_length)

        return np.interp(new_indices, old_indices, pcm16).astype(np.int16)

    @staticmethod
    def estimate_duration(text: str, speed: float = 1.0) -> int:
        """Estimate audio duration for text at given speed.

        Uses average speaking rate of ~150 words per minute.

        Args:
            text: Text to estimate.
            speed: Speaking speed multiplier.

        Returns:
            Estimated duration in milliseconds.
        """
        word_count = len(text.split())
        # ~150 WPM = 400ms per word
        ms_per_word = 400 / max(speed, 0.1)
        return int(word_count * ms_per_word)

    @staticmethod
    def create_wav_bytes(
        pcm16: np.ndarray,
        sample_rate: int = 22050,
    ) -> bytes:
        """Create WAV file bytes from PCM16 audio.

        Args:
            pcm16: 16-bit PCM audio data.
            sample_rate: Sample rate.

        Returns:
            WAV file bytes.
        """
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(pcm16.tobytes())
        return buffer.getvalue()

    def select_voice_for_tenant(
        self,
        tenant_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Select appropriate voice based on tenant configuration.

        Args:
            tenant_config: Tenant voice preferences.

        Returns:
            Selected voice ID.
        """
        if not tenant_config:
            return self.default_voice

        preferred = tenant_config.get("voice_id")
        if preferred and preferred in ["lessac-medium", "lessac-low", "amy-medium"]:
            return preferred

        # Select based on quality preference
        quality = tenant_config.get("voice_quality", "medium")
        if quality == "high":
            return "lessac-medium"
        elif quality == "low":
            return "lessac-low"

        return self.default_voice


# ---------------------------------------------------------------------------
#  Factory functions
# ---------------------------------------------------------------------------

_piper_service_instance: Optional[PiperService] = None


async def get_piper_service() -> PiperService:
    """Get or create singleton PiperService instance.

    Returns:
        Configured PiperService instance.
    """
    global _piper_service_instance
    if _piper_service_instance is None:
        _piper_service_instance = PiperService(
            base_url="http://localhost:8082",
            default_voice=TTSConfig.DEFAULT_VOICE,
            timeout=15.0,
            max_retries=3,
        )
        await _piper_service_instance.start()
    return _piper_service_instance


async def close_piper_service() -> None:
    """Close singleton instance."""
    global _piper_service_instance
    if _piper_service_instance:
        await _piper_service_instance.stop()
        _piper_service_instance = None
