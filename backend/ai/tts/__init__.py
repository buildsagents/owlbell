"""
Text-to-Speech (TTS) module.

Provides speech synthesis via Piper TTS server.
"""

from backend.ai.tts.piper_service import (
    TTSConfig,
    TTSRequest,
    TTSResult,
    PiperService,
    PiperServiceError,
    get_piper_service,
    close_piper_service,
)

__all__ = [
    "TTSConfig",
    "TTSRequest",
    "TTSResult",
    "PiperService",
    "PiperServiceError",
    "get_piper_service",
    "close_piper_service",
]
