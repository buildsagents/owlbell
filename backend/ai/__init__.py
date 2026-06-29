"""
Owlbell - AI Conversation Pipeline.

Core AI engine for real-time voice conversations.
Pipeline: Audio -> STT -> LLM -> TTS -> Audio
"""

from __future__ import annotations

import sys

from backend.import_roots import ensure_import_paths, register_namespace_alias

ensure_import_paths()
register_namespace_alias(sys.modules[__name__])

from backend.ai.stt.whisper_service import WhisperService, get_whisper_service
from backend.ai.llm.ollama_client import OllamaClient, get_ollama_client
from backend.ai.tts.piper_service import PiperService, get_piper_service

__all__ = [
    "WhisperService",
    "get_whisper_service",
    "OllamaClient",
    "get_ollama_client",
    "PiperService",
    "get_piper_service",
]
