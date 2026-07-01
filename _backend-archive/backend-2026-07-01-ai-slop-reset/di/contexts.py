"""Service context objects managed by the DI container."""

from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AIPipelineContext:
    """Lazy-loading wrapper for AI pipeline services."""

    def __init__(self) -> None:
        self._whisper = None
        self._ollama = None
        self._piper = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        try:
            from backend.ai.stt.whisper_service import get_whisper_service
            from backend.ai.llm.ollama_client import get_ollama_client
            from backend.ai.tts.piper_service import get_piper_service

            self._whisper = await get_whisper_service()
            self._ollama = await get_ollama_client()
            self._piper = await get_piper_service()
            self._initialized = True
            logger.info("di.ai_pipeline_initialized")
        except Exception as exc:
            logger.error("di.ai_pipeline_init_failed", extra={"error": str(exc)})
            raise

    @property
    def whisper(self):
        return self._whisper

    @property
    def ollama(self):
        return self._ollama

    @property
    def piper(self):
        return self._piper

    async def health_check(self) -> Dict[str, bool]:
        results = {"whisper": False, "ollama": False, "piper": False}
        if self._whisper is not None:
            try:
                results["whisper"] = await self._whisper.is_healthy()
            except Exception:
                pass
        if self._ollama is not None:
            try:
                results["ollama"] = await self._ollama.is_healthy()
            except Exception:
                pass
        if self._piper is not None:
            try:
                results["piper"] = await self._piper.is_healthy()
            except Exception:
                pass
        return results


class CallManagerContext:
    """Context providing access to telephony services."""

    def __init__(self) -> None:
        self._esl_client = None
        self._session_manager = None
        self._event_bus = None

    async def initialize(self) -> None:
        try:
            from orchestrator.event_bus import EventBus
            from orchestrator.session_manager import SessionManager

            from backend.db.cache.client import get_redis_client

            redis_client = await get_redis_client()
            self._session_manager = SessionManager(redis_client)
            self._event_bus = EventBus(redis_client)
            logger.info("di.call_manager_initialized")
        except Exception as exc:
            logger.error("di.call_manager_init_failed", extra={"error": str(exc)})

    @property
    def session_manager(self):
        return self._session_manager

    @property
    def event_bus(self):
        return self._event_bus


__all__ = ["AIPipelineContext", "CallManagerContext"]