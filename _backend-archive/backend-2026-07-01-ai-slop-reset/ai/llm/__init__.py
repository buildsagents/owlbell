"""
LLM Engine module.

Provides LLM inference via Ollama server with streaming,
tool calling, and model fallback support.
"""

from backend.ai.llm.ollama_client import (
    LLMMessage,
    LLMResponse,
    OllamaClient,
    OllamaError,
    OllamaModelError,
    OllamaUnavailable,
    StreamingToken,
    get_ollama_client,
    close_ollama_client,
)

__all__ = [
    "LLMMessage",
    "LLMResponse",
    "StreamingToken",
    "OllamaClient",
    "OllamaError",
    "OllamaModelError",
    "OllamaUnavailable",
    "get_ollama_client",
    "close_ollama_client",
]
