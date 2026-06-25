"""
Ollama HTTP client for LLM inference.

Provides streaming and non-streaming chat completion via Ollama's API.
Handles tool calling, prompt formatting, system prompt management per tenant,
conversation history management, model fallback chain, token counting,
and response parsing and validation.

Usage:
    client = OllamaClient()
    response = await client.chat(messages, tools=available_tools)
    async for token in client.chat_stream(messages):
        print(token, end="")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
)
from urllib.parse import urljoin

import aiohttp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  Fallback chain & model specs
# ---------------------------------------------------------------------------


class ModelTier(str, Enum):
    """Quality tier for model selection."""

    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


@dataclass
class ModelSpec:
    """Specification for an available LLM."""

    name: str
    display_name: str
    tier: ModelTier
    vram_gb: float
    context_length: int
    avg_tok_per_sec: int
    quantization: str
    supports_tools: bool
    description: str


AVAILABLE_MODELS: Dict[str, ModelSpec] = {
    "llama3.2:3b": ModelSpec(
        name="llama3.2:3b",
        display_name="Llama 3.2 3B",
        tier=ModelTier.FAST,
        vram_gb=2.0,
        context_length=8192,
        avg_tok_per_sec=80,
        quantization="Q4_K_M",
        supports_tools=True,
        description="Fast, good for multiple concurrent calls. Default choice.",
    ),
    "phi3:mini": ModelSpec(
        name="phi3:mini",
        display_name="Phi-3 Mini",
        tier=ModelTier.FAST,
        vram_gb=1.5,
        context_length=8192,
        avg_tok_per_sec=100,
        quantization="Q4_K_M",
        supports_tools=True,
        description="Fastest option, lowest VRAM. Good for simple conversations.",
    ),
    "mistral": ModelSpec(
        name="mistral",
        display_name="Mistral 7B",
        tier=ModelTier.BALANCED,
        vram_gb=4.5,
        context_length=8192,
        avg_tok_per_sec=40,
        quantization="Q4_K_M",
        supports_tools=True,
        description="Good quality for complex conversations. Fits 2-3 concurrent.",
    ),
    "llama3.1:8b": ModelSpec(
        name="llama3.1:8b",
        display_name="Llama 3.1 8B",
        tier=ModelTier.QUALITY,
        vram_gb=5.5,
        context_length=8192,
        avg_tok_per_sec=35,
        quantization="Q4_K_M",
        supports_tools=True,
        description="Best quality. Use for single high-value calls.",
    ),
}

DEFAULT_MODEL = "llama3.2:3b"
FALLBACK_CHAIN = ["llama3.2:3b", "phi3:mini", "mistral"]


# ---------------------------------------------------------------------------
#  Data models
# ---------------------------------------------------------------------------


@dataclass
class LLMMessage:
    """Single message in a conversation.

    Attributes:
        role: Message role (system, user, assistant, tool).
        content: Message content text.
        tool_calls: Optional tool calls from assistant.
        tool_call_id: Optional tool call ID for tool responses.
    """

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, str]:
        """Convert to Ollama API message format."""
        msg: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        return msg


@dataclass
class LLMResponse:
    """Response from LLM chat completion.

    Attributes:
        content: Generated text content.
        tool_calls: List of extracted tool calls.
        model_used: Which model generated the response.
        total_tokens: Total tokens used.
        prompt_tokens: Input prompt tokens.
        completion_tokens: Generated tokens.
        latency_ms: Response time in milliseconds.
        finish_reason: Why generation stopped.
        is_error: Whether this is a fallback error response.
        error_message: Error description if is_error=True.
    """

    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    model_used: str = ""
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    finish_reason: str = ""
    is_error: bool = False
    error_message: str = ""


@dataclass
class StreamingToken:
    """Single token from streaming response.

    Attributes:
        content: Text content of this token.
        tool_call_chunk: Partial or complete tool call data.
        is_finished: Whether generation is complete.
        finish_reason: Reason for completion.
    """

    content: str = ""
    tool_call_chunk: Optional[Dict[str, Any]] = None
    is_finished: bool = False
    finish_reason: str = ""


@dataclass
class ToolCall:
    """Parsed tool call from LLM response.

    Attributes:
        name: Tool/function name.
        parameters: Tool arguments as dict.
        raw: Raw tool call string from LLM.
    """

    name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    raw: str = ""


# ---------------------------------------------------------------------------
#  Exceptions
# ---------------------------------------------------------------------------


class OllamaError(Exception):
    """Base exception for Ollama client."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        model: str = "",
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.model = model
        self.recoverable = recoverable


class OllamaUnavailable(OllamaError):
    """Ollama server is not reachable."""

    pass


class OllamaModelError(OllamaError):
    """Error loading or running a specific model."""

    pass


# ---------------------------------------------------------------------------
#  Tool call parser
# ---------------------------------------------------------------------------


class ToolCallParser:
    """Parse tool calls from LLM text output.

    Supports both explicit XML-style tags and JSON-style tool calls.
    """

    # XML-style: <tool_call name="xxx">{...}</tool_call>
    XML_PATTERN = "<tool_call"
    XML_END = "</tool_call>"

    # JSON-style markers
    JSON_START = "{"
    JSON_END = "}"

    def __init__(self) -> None:
        self._buffer: str = ""

    def reset(self) -> None:
        """Clear internal buffer."""
        self._buffer = ""

    def extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Extract all complete tool calls from text.

        Args:
            text: Full LLM response text.

        Returns:
            List of tool call dicts with name and parameters.
        """
        calls: List[Dict[str, Any]] = []

        # Try XML-style extraction
        idx = 0
        while True:
            start = text.find(self.XML_PATTERN, idx)
            if start == -1:
                break
            end = text.find(self.XML_END, start)
            if end == -1:
                break
            end += len(self.XML_END)
            raw = text[start:end]
            parsed = self._parse_xml_tool_call(raw)
            if parsed:
                calls.append(parsed)
            idx = end

        # Try JSON-style extraction if no XML found
        if not calls:
            try:
                data = json.loads(text.strip())
                if isinstance(data, dict) and "tool" in data:
                    calls.append(
                        {
                            "name": data["tool"],
                            "parameters": data.get("parameters", {}),
                            "raw": text.strip(),
                        }
                    )
            except (json.JSONDecodeError, KeyError):
                pass

        return calls

    def extract_tool_call_partial(
        self, buffer: str
    ) -> Optional[Dict[str, Any]]:
        """Check if buffer contains a complete tool call.

        Args:
            buffer: Current text buffer.

        Returns:
            Dict with tool call data if complete, None otherwise.
        """
        start = buffer.rfind(self.XML_PATTERN)
        if start == -1:
            return None
        end = buffer.find(self.XML_END, start)
        if end == -1:
            return {"is_complete": False}
        end += len(self.XML_END)
        raw = buffer[start:end]
        parsed = self._parse_xml_tool_call(raw)
        if parsed:
            parsed["is_complete"] = True
        return parsed

    def _parse_xml_tool_call(self, raw: str) -> Optional[Dict[str, Any]]:
        """Parse an XML-style tool call string.

        Args:
            raw: Raw tool call XML string.

        Returns:
            Parsed tool call dict or None.
        """
        try:
            # Extract name from opening tag
            name_start = raw.find('name="')
            if name_start == -1:
                return None
            name_start += 6
            name_end = raw.find('"', name_start)
            name = raw[name_start:name_end]

            # Extract JSON parameters between tags
            json_start = raw.find(">", raw.find("<tool_call")) + 1
            json_end = raw.find("</tool_call>")
            json_str = raw[json_start:json_end].strip()
            parameters = json.loads(json_str) if json_str else {}

            return {"name": name, "parameters": parameters, "raw": raw}
        except (json.JSONDecodeError, IndexError) as exc:
            logger.debug(f"Failed to parse tool call: {exc}")
            return None

    def strip_tool_calls(self, text: str) -> str:
        """Remove tool call XML from text, return clean content.

        Args:
            text: Raw LLM response.

        Returns:
            Text with tool calls removed.
        """
        result = text
        while self.XML_PATTERN in result:
            start = result.find(self.XML_PATTERN)
            end = result.find(self.XML_END, start)
            if end == -1:
                break
            end += len(self.XML_END)
            result = result[:start].strip() + " " + result[end:].strip()
        return result.strip()


# ---------------------------------------------------------------------------
#  System prompt manager
# ---------------------------------------------------------------------------


class SystemPromptManager:
    """Manages system prompts per tenant with caching.

    Attributes:
        _cache: In-memory cache of system prompts keyed by tenant_id.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, str] = {}
        self._base_prompt: str = (
            "You are the AI phone assistant for {business_name}. You are "
            "professional, friendly, and efficient. Your goal is to help callers "
            "by answering questions, scheduling appointments, taking messages, "
            "or transferring calls when needed.\n\n"
            "## Personality\n"
            "- Speak naturally and warmly, like a helpful receptionist\n"
            "- Keep responses concise (2-3 sentences typical)\n"
            "- Ask clarifying questions when needed\n"
            "- Always confirm important details (dates, times, names)\n\n"
            "## Rules\n"
            "1. NEVER make up information. If unsure, say you'll take a message.\n"
            "2. ALWAYS confirm appointment times before booking.\n"
            "3. If caller asks for a human, offer to transfer immediately.\n"
            "4. Collect: name, phone number, and reason for call.\n"
            "5. Protect privacy: never share other clients' information.\n\n"
            "## Current Time\n"
            "It is currently {current_time} on {current_day}, {current_date}.\n\n"
            "{caller_info}\n{tools_info}"
        )

    def build_prompt(
        self,
        business_context: Dict[str, Any],
        caller_profile: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build system prompt for a tenant.

        Args:
            business_context: Business info (name, hours, services).
            caller_profile: Known caller info.
            available_tools: Available tool descriptions.

        Returns:
            Formatted system prompt string.
        """
        import datetime as dt

        now = dt.datetime.now()

        caller_info = ""
        if caller_profile:
            parts = ["## Caller Information"]
            if caller_profile.get("preferred_name"):
                parts.append(f"Name: {caller_profile['preferred_name']}")
            if caller_profile.get("last_call_at"):
                parts.append(f"Last call: {caller_profile['last_call_at']}")
            if caller_profile.get("typical_reason"):
                parts.append(f"Usually calls about: {caller_profile['typical_reason']}")
            caller_info = "\n".join(parts)

        tools_info = ""
        if available_tools:
            parts = ["\n## Available Tools\n"]
            for tool in available_tools:
                parts.append(f"### {tool['function']['name']}")
                parts.append(f"Description: {tool['function']['description']}")
                params = tool["function"].get("parameters", {})
                if params:
                    parts.append("Parameters:")
                    for prop_name, prop_info in params.get("properties", {}).items():
                        parts.append(
                            f"  - {prop_name}: {prop_info.get('type', 'string')}"
                            f" - {prop_info.get('description', '')}"
                        )
            tools_info = "\n".join(parts)

        prompt = self._base_prompt.format(
            business_name=business_context.get("name", "the business"),
            current_time=now.strftime("%I:%M %p"),
            current_day=now.strftime("%A"),
            current_date=now.strftime("%B %d, %Y"),
            caller_info=caller_info,
            tools_info=tools_info,
        )
        return prompt

    def get_cached_prompt(self, tenant_id: str) -> Optional[str]:
        """Get cached system prompt for a tenant.

        Args:
            tenant_id: Tenant UUID.

        Returns:
            Cached prompt or None.
        """
        return self._cache.get(tenant_id)

    def cache_prompt(self, tenant_id: str, prompt: str) -> None:
        """Cache system prompt for a tenant.

        Args:
            tenant_id: Tenant UUID.
            prompt: System prompt to cache.
        """
        self._cache[tenant_id] = prompt

    def invalidate_cache(self, tenant_id: str) -> None:
        """Remove cached prompt for a tenant.

        Args:
            tenant_id: Tenant UUID.
        """
        self._cache.pop(tenant_id, None)


# ---------------------------------------------------------------------------
#  Conversation history manager
# ---------------------------------------------------------------------------


class ConversationHistoryManager:
    """Manages conversation history with context window management.

    Trims old messages to fit within the model's context window while
    always preserving the system prompt and most recent messages.

    Attributes:
        max_context_tokens: Maximum tokens for history (excluding system).
        chars_per_token: Approximate characters per token for estimation.
    """

    def __init__(
        self,
        max_context_tokens: int = 6144,
        chars_per_token: int = 4,
    ) -> None:
        self.max_context_tokens = max_context_tokens
        self.chars_per_token = chars_per_token
        self._histories: Dict[str, List[Dict[str, str]]] = {}

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a session.

        Args:
            session_id: Session identifier.

        Returns:
            List of message dicts in OpenAI format.
        """
        return self._histories.get(session_id, []).copy()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """Add a message to the conversation history.

        Args:
            session_id: Session identifier.
            role: Message role.
            content: Message content.
        """
        if session_id not in self._histories:
            self._histories[session_id] = []
        self._histories[session_id].append(
            {"role": role, "content": content}
        )

    def trim_history(self, session_id: str) -> List[Dict[str, str]]:
        """Trim history to fit within context window.

        Keeps most recent messages, drops oldest ones first.

        Args:
            session_id: Session identifier.

        Returns:
            Trimmed history list.
        """
        history = self._histories.get(session_id, [])
        if not history:
            return []

        total_chars = sum(len(m["content"]) for m in history)
        estimated_tokens = total_chars // self.chars_per_token

        while estimated_tokens > self.max_context_tokens and len(history) > 2:
            removed = history.pop(0)
            estimated_tokens -= len(removed["content"]) // self.chars_per_token

        return history

    def build_messages(
        self,
        session_id: str,
        system_prompt: str,
        new_user_message: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Build complete message list for LLM API.

        Manages context window by trimming old history if needed.

        Args:
            session_id: Session identifier.
            system_prompt: System prompt string.
            new_user_message: New caller message to append.

        Returns:
            OpenAI-format message list.
        """
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]

        # Calculate remaining token budget
        system_tokens = len(system_prompt) // self.chars_per_token
        remaining_tokens = self.max_context_tokens - system_tokens

        # Get trimmed history
        history = self.trim_history(session_id)

        # Add history, newest first, until budget exhausted
        selected_history: List[Dict[str, str]] = []
        history_tokens = 0

        for msg in reversed(history):
            msg_tokens = len(msg.get("content", "")) // self.chars_per_token
            if history_tokens + msg_tokens > remaining_tokens:
                break
            selected_history.insert(0, msg)
            history_tokens += msg_tokens

        messages.extend(selected_history)

        # Add new user message
        if new_user_message:
            messages.append({"role": "user", "content": new_user_message})

        return messages

    def clear_history(self, session_id: str) -> None:
        """Clear conversation history for a session.

        Args:
            session_id: Session identifier.
        """
        self._histories.pop(session_id, None)

    def add_tool_result(
        self,
        session_id: str,
        tool_name: str,
        tool_result: Dict[str, Any],
    ) -> None:
        """Add tool result as a tool message.

        Args:
            session_id: Session identifier.
            tool_name: Name of the tool.
            tool_result: Result dict from tool execution.
        """
        result_text = json.dumps(
            {"tool": tool_name, "result": tool_result}, indent=2
        )
        self.add_message(session_id, "tool", result_text)


# ---------------------------------------------------------------------------
#  Ollama client
# ---------------------------------------------------------------------------


class OllamaClient:
    """Async client for Ollama LLM server.

    Features:
    - Streaming and non-streaming chat completion.
    - Automatic model fallback on failure.
    - Tool call extraction and parsing.
    - Token counting and latency tracking.
    - Connection pooling and health checks.
    - Per-tenant system prompt management.
    - Conversation history with context window management.

    Args:
        base_url: Ollama server URL.
        default_model: Default model to use.
        timeout: Request timeout in seconds.
        max_retries: Max retries per model.
        streaming_timeout: Timeout for streaming chunks.
    """

    DEFAULT_TEMPERATURE: float = 0.7
    DEFAULT_TOP_P: float = 0.9
    DEFAULT_TOP_K: int = 40
    DEFAULT_REPEAT_PENALTY: float = 1.1

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = DEFAULT_MODEL,
        timeout: float = 30.0,
        max_retries: int = 2,
        streaming_timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries
        self.streaming_timeout = streaming_timeout

        self._session: Optional[aiohttp.ClientSession] = None
        self._is_healthy: bool = False
        self._loaded_models: set = set()
        self._tool_parser = ToolCallParser()
        self._prompt_manager = SystemPromptManager()
        self._history_manager = ConversationHistoryManager()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._session

    async def start(self) -> None:
        """Initialize client, check server health, preload default model."""
        await self._get_session()

        if await self.health_check():
            try:
                await self._load_model(self.default_model)
                self._loaded_models.add(self.default_model)
                logger.info(
                    f"OllamaClient started, default model "
                    f"'{self.default_model}' loaded"
                )
            except Exception as exc:
                logger.warning(f"Failed to preload default model: {exc}")
        else:
            logger.warning("Ollama server not healthy at startup")

    async def stop(self) -> None:
        """Cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        logger.info("OllamaClient stopped")

    async def health_check(self) -> bool:
        """Check if Ollama server is running."""
        try:
            session = await self._get_session()
            async with session.get(
                urljoin(self.base_url, "/api/tags"),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                self._is_healthy = resp.status == 200
                if self._is_healthy:
                    data = await resp.json()
                    available = [m["name"] for m in data.get("models", [])]
                    logger.debug(f"Ollama healthy, models: {available}")
                return self._is_healthy
        except Exception as exc:
            logger.warning(f"Ollama health check failed: {exc}")
            self._is_healthy = False
            return False

    @property
    def is_healthy(self) -> bool:
        """Return cached health status."""
        return self._is_healthy

    async def _load_model(self, model_name: str) -> None:
        """Pre-load a model into GPU memory."""
        logger.info(f"Loading model: {model_name}")
        session = await self._get_session()

        async with session.post(
            urljoin(self.base_url, "/api/generate"),
            json={"model": model_name, "prompt": "", "keep_alive": "30m"},
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status == 200:
                async for _ in resp.content:
                    pass
                self._loaded_models.add(model_name)
                logger.info(f"Model {model_name} loaded successfully")
            else:
                body = await resp.text()
                raise OllamaModelError(
                    f"Failed to load model {model_name}: {body}",
                    status_code=resp.status,
                    model=model_name,
                )

    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = 256,
        stream: bool = False,
        format_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build Ollama API request payload.

        Args:
            messages: OpenAI-format message list.
            model: Model name to use.
            tools: Available tools for function calling.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            stream: Whether to stream response.
            format_schema: JSON schema for structured output.

        Returns:
            API payload dict.
        """
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": self.DEFAULT_TOP_P,
                "top_k": self.DEFAULT_TOP_K,
                "repeat_penalty": self.DEFAULT_REPEAT_PENALTY,
                "stop": ["<|im_end|>", "<|end|>", "Human:", "User:"],
            },
        }

        if tools:
            payload["tools"] = tools

        if format_schema:
            payload["format"] = format_schema

        return payload

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = 256,
        format_schema: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Non-streaming chat completion.

        Args:
            messages: OpenAI-format message list.
            model: Model to use (default: self.default_model).
            tools: Available tools for function calling.
            temperature: Sampling temperature (0.0-1.0).
            max_tokens: Maximum tokens to generate.
            format_schema: JSON schema for structured output.

        Returns:
            LLMResponse with content, tool_calls, and metadata.

        Raises:
            OllamaUnavailable: Server not reachable.
            OllamaModelError: Model-specific error.
        """
        model = model or self.default_model
        start_time = time.perf_counter()

        models_to_try = [model] + [m for m in FALLBACK_CHAIN if m != model]
        last_error: Optional[Exception] = None

        for try_model in models_to_try:
            for attempt in range(1, self.max_retries + 1):
                try:
                    if try_model not in self._loaded_models:
                        await self._load_model(try_model)

                    payload = self._build_payload(
                        messages=messages,
                        model=try_model,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=False,
                        format_schema=format_schema,
                    )

                    session = await self._get_session()
                    async with session.post(
                        urljoin(self.base_url, "/api/chat"),
                        json=payload,
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()

                            latency = int(
                                (time.perf_counter() - start_time) * 1000
                            )

                            message = result.get("message", {})
                            content = message.get("content", "")

                            # Extract tool calls
                            tool_calls = self._tool_parser.extract_tool_calls(
                                content
                            )

                            # Strip tool calls from displayed content
                            clean_content = self._tool_parser.strip_tool_calls(
                                content
                            )

                            return LLMResponse(
                                content=clean_content,
                                tool_calls=tool_calls,
                                model_used=try_model,
                                total_tokens=result.get(
                                    "prompt_eval_count", 0
                                )
                                + result.get("eval_count", 0),
                                prompt_tokens=result.get(
                                    "prompt_eval_count", 0
                                ),
                                completion_tokens=result.get("eval_count", 0),
                                latency_ms=latency,
                                finish_reason=result.get("done_reason", "stop"),
                            )

                        elif resp.status == 404:
                            logger.warning(
                                f"Model {try_model} not loaded, attempting load"
                            )
                            await self._load_model(try_model)
                            continue

                        else:
                            body = await resp.text()
                            raise OllamaModelError(
                                f"Ollama error {resp.status}: {body}",
                                status_code=resp.status,
                                model=try_model,
                            )

                except asyncio.TimeoutError:
                    logger.warning(
                        f"Timeout with {try_model} (attempt {attempt})"
                    )
                    last_error = OllamaUnavailable(
                        f"Timeout (model={try_model}, attempt={attempt})",
                        model=try_model,
                    )

                except aiohttp.ClientError as exc:
                    logger.warning(
                        f"Connection error: {exc} (model={try_model})"
                    )
                    self._is_healthy = False
                    last_error = OllamaUnavailable(
                        f"Connection error: {exc}",
                        model=try_model,
                    )

                except OllamaModelError as exc:
                    logger.warning(f"Model error: {exc}")
                    last_error = exc
                    if not exc.recoverable:
                        break

                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * attempt)

        # All models exhausted
        error_msg = f"All models failed. Last error: {last_error}"
        logger.error(error_msg)
        return LLMResponse(
            content=(
                "I'm having trouble processing your request. "
                "Could you please repeat that?"
            ),
            is_error=True,
            error_message=error_msg,
            model_used=model,
            latency_ms=int((time.perf_counter() - start_time) * 1000),
        )

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = 256,
    ) -> AsyncGenerator[StreamingToken, None]:
        """Streaming chat completion.

        Yields tokens as they are generated. Much faster perceived latency
        since TTS can begin before the full response is received.

        Args:
            messages: OpenAI-format message list.
            model: Model to use (default: self.default_model).
            tools: Available tools for function calling.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.

        Yields:
            StreamingToken chunks.
        """
        model = model or self.default_model
        models_to_try = [model] + [m for m in FALLBACK_CHAIN if m != model]

        for try_model in models_to_try:
            try:
                if try_model not in self._loaded_models:
                    await self._load_model(try_model)

                payload = self._build_payload(
                    messages=messages,
                    model=try_model,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )

                session = await self._get_session()
                buffer = ""

                async with session.post(
                    urljoin(self.base_url, "/api/chat"),
                    json=payload,
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(f"Stream error {resp.status}: {body}")
                        yield StreamingToken(
                            content="",
                            is_finished=True,
                            finish_reason="error",
                        )
                        return

                    async for line in resp.content:
                        if not line.strip():
                            continue

                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        message = chunk.get("message", {})
                        token = message.get("content", "")

                        if token:
                            buffer += token

                            # Check if buffer contains tool call
                            tool_call = (
                                self._tool_parser.extract_tool_call_partial(
                                    buffer
                                )
                            )

                            if tool_call and tool_call.get("is_complete"):
                                yield StreamingToken(
                                    content="",
                                    tool_call_chunk=tool_call,
                                )
                                buffer = ""
                            elif not tool_call:
                                # Regular text token
                                yield StreamingToken(content=token)

                        # Check if generation is complete
                        if chunk.get("done"):
                            final_tools = self._tool_parser.extract_tool_calls(
                                buffer
                            )
                            for tool in final_tools:
                                yield StreamingToken(
                                    content="",
                                    tool_call_chunk=tool,
                                )

                            yield StreamingToken(
                                content="",
                                is_finished=True,
                                finish_reason=chunk.get("done_reason", "stop"),
                            )
                            return

                # Stream completed normally
                return

            except Exception as exc:
                logger.warning(f"Stream failed with {try_model}: {exc}")
                continue

        # All models failed
        logger.error("Streaming failed for all models")
        yield StreamingToken(
            content="I'm having trouble. Could you repeat that?",
            is_finished=True,
            finish_reason="error",
        )

    # ------------------------------------------------------------------ #
    #  Convenience helpers
    # ------------------------------------------------------------------ #

    def build_system_prompt(
        self,
        business_context: Dict[str, Any],
        caller_profile: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build system prompt for a tenant.

        Args:
            business_context: Business info dict.
            caller_profile: Optional caller profile.
            available_tools: Optional tool descriptions.

        Returns:
            Formatted system prompt.
        """
        return self._prompt_manager.build_prompt(
            business_context, caller_profile, available_tools
        )

    def get_cached_prompt(self, tenant_id: str) -> Optional[str]:
        """Get cached system prompt for a tenant.

        Args:
            tenant_id: Tenant UUID.

        Returns:
            Cached prompt or None.
        """
        return self._prompt_manager.get_cached_prompt(tenant_id)

    def cache_prompt(self, tenant_id: str, prompt: str) -> None:
        """Cache a system prompt for a tenant.

        Args:
            tenant_id: Tenant UUID.
            prompt: System prompt string.
        """
        self._prompt_manager.cache_prompt(tenant_id, prompt)

    def add_message_to_history(
        self, session_id: str, role: str, content: str
    ) -> None:
        """Add a message to conversation history.

        Args:
            session_id: Session identifier.
            role: Message role.
            content: Message content.
        """
        self._history_manager.add_message(session_id, role, content)

    def build_messages_with_history(
        self,
        session_id: str,
        system_prompt: str,
        new_user_message: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Build messages including conversation history.

        Args:
            session_id: Session identifier.
            system_prompt: System prompt.
            new_user_message: New user message.

        Returns:
            Complete message list for LLM API.
        """
        return self._history_manager.build_messages(
            session_id, system_prompt, new_user_message
        )

    def clear_conversation_history(self, session_id: str) -> None:
        """Clear conversation history for a session.

        Args:
            session_id: Session identifier.
        """
        self._history_manager.clear_history(session_id)

    def count_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses a simple character-based heuristic (~4 chars per token).

        Args:
            text: Input text.

        Returns:
            Estimated token count.
        """
        return max(1, len(text) // 4)

    def count_message_tokens(
        self, messages: List[Dict[str, str]]
    ) -> int:
        """Estimate total tokens for a message list.

        Args:
            messages: OpenAI-format messages.

        Returns:
            Estimated total tokens.
        """
        return sum(self.count_tokens(m.get("content", "")) for m in messages)

    def check_context_fit(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
    ) -> bool:
        """Check if messages fit within model context window.

        Args:
            messages: Message list to check.
            model: Model name (for context length lookup).

        Returns:
            True if messages fit within context window.
        """
        model = model or self.default_model
        spec = AVAILABLE_MODELS.get(model)
        if not spec:
            return True
        estimated = self.count_message_tokens(messages)
        return estimated < spec.context_length


# ---------------------------------------------------------------------------
#  Factory functions
# ---------------------------------------------------------------------------

_ollama_client_instance: Optional[OllamaClient] = None


async def get_ollama_client() -> OllamaClient:
    """Get or create singleton OllamaClient instance.

    Returns:
        Configured OllamaClient instance.
    """
    global _ollama_client_instance
    if _ollama_client_instance is None:
        _ollama_client_instance = OllamaClient(
            base_url="http://localhost:11434",
            default_model=DEFAULT_MODEL,
            timeout=30.0,
            max_retries=2,
            streaming_timeout=10.0,
        )
        await _ollama_client_instance.start()
    return _ollama_client_instance


async def close_ollama_client() -> None:
    """Close the singleton instance."""
    global _ollama_client_instance
    if _ollama_client_instance:
        await _ollama_client_instance.stop()
        _ollama_client_instance = None
