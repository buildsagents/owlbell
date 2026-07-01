"""
Speech-to-Text (STT) module.

Provides speech transcription via whisper.cpp server.
"""

from backend.ai.stt.whisper_service import (
    STTResult,
    WhisperService,
    WhisperServiceError,
    WhisperServiceUnavailable,
    WhisperTranscriptionError,
    get_whisper_service,
    close_whisper_service,
)

__all__ = [
    "STTResult",
    "WhisperService",
    "WhisperServiceError",
    "WhisperServiceUnavailable",
    "WhisperTranscriptionError",
    "get_whisper_service",
    "close_whisper_service",
]
