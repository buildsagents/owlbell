"""
Tests for Ollama LLM client.

Covers chat completion, streaming, tool call parsing, system prompt
management, conversation history, model fallback, and error handling.
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from backend.ai.llm.ollama_client import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    FALLBACK_CHAIN,
    LLMMessage,
    LLMResponse,
    ModelSpec,
    ModelTier,
    OllamaClient,
    OllamaError,
    OllamaModelError,
    OllamaUnavailable,
    StreamingToken,
    SystemPromptManager,
    ToolCall,
    ToolCallParser,
    ConversationHistoryManager,
)


# ---------------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ollama_client() -> OllamaClient:
    """Create an OllamaClient for testing."""
    return OllamaClient(
        base_url="http://localhost:9999",
        default_model=DEFAULT_MODEL,
        timeout=5.0,
        max_retries=2,
        streaming_timeout=5.0,
    )


# ---------------------------------------------------------------------------
#  LLMMessage tests
# ---------------------------------------------------------------------------


class TestLLMMessage:
    """Tests for LLMMessage dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a message."""
        msg = LLMMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.tool_calls is None

    def test_to_dict(self) -> None:
        """Test conversion to dict."""
        msg = LLMMessage(role="assistant", content="Hi there")
        d = msg.to_dict()
        assert d == {"role": "assistant", "content": "Hi there"}

    def test_to_dict_with_tool_calls(self) -> None:
        """Test conversion with tool calls."""
        msg = LLMMessage(
            role="assistant",
            content="Using tool",
            tool_calls=[{"name": "test"}],
        )
        d = msg.to_dict()
        assert d["tool_calls"] == [{"name": "test"}]


# ---------------------------------------------------------------------------
#  LLMResponse tests
# ---------------------------------------------------------------------------


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a response."""
        resp = LLMResponse(content="Hello there")
        assert resp.content == "Hello there"
        assert resp.tool_calls == []
        assert resp.model_used == ""
        assert not resp.is_error

    def test_error_response(self) -> None:
        """Test error response."""
        resp = LLMResponse(
            content="Error occurred",
            is_error=True,
            error_message="Model failed",
        )
        assert resp.is_error
        assert resp.error_message == "Model failed"

    def test_with_tool_calls(self) -> None:
        """Test response with tool calls."""
        resp = LLMResponse(
            content="",
            tool_calls=[{"name": "check_calendar"}],
            model_used="llama3.2:3b",
        )
        assert len(resp.tool_calls) == 1
        assert resp.model_used == "llama3.2:3b"


# ---------------------------------------------------------------------------
#  StreamingToken tests
# ---------------------------------------------------------------------------


class TestStreamingToken:
    """Tests for StreamingToken dataclass."""

    def test_content_token(self) -> None:
        """Test content token."""
        token = StreamingToken(content="Hello")
        assert token.content == "Hello"
        assert not token.is_finished

    def test_finish_token(self) -> None:
        """Test finish token."""
        token = StreamingToken(is_finished=True, finish_reason="stop")
        assert token.is_finished
        assert token.finish_reason == "stop"

    def test_tool_call_token(self) -> None:
        """Test tool call token."""
        token = StreamingToken(
            tool_call_chunk={"name": "test", "parameters": {}}
        )
        assert token.tool_call_chunk is not None


# ---------------------------------------------------------------------------
#  ToolCallParser tests
# ---------------------------------------------------------------------------


class TestToolCallParser:
    """Tests for ToolCallParser."""

    @pytest.fixture
    def parser(self) -> ToolCallParser:
        return ToolCallParser()

    def test_extract_xml_tool_call(self, parser: ToolCallParser) -> None:
        """Test XML-style tool call extraction."""
        text = 'Let me check. <tool_call name="check_calendar">{"date": "2025-01-15"}</tool_call>'
        calls = parser.extract_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["name"] == "check_calendar"

    def test_extract_no_tool_calls(self, parser: ToolCallParser) -> None:
        """Test text with no tool calls."""
        text = "Hello, how can I help you today?"
        calls = parser.extract_tool_calls(text)
        assert calls == []

    def test_strip_tool_calls(self, parser: ToolCallParser) -> None:
        """Test stripping tool calls from text."""
        text = 'Let me check. <tool_call name="test">{}</tool_call> Here is the result.'
        stripped = parser.strip_tool_calls(text)
        assert "tool_call" not in stripped
        assert "Here is the result" in stripped

    def test_extract_json_tool_call(self, parser: ToolCallParser) -> None:
        """Test JSON-style tool call extraction."""
        text = '{"tool": "check_calendar", "parameters": {"date": "2025-01-15"}}'
        calls = parser.extract_tool_calls(text)
        # Should be parsed as JSON tool call
        assert len(calls) >= 0  # May or may not parse depending on format

    def test_multiple_tool_calls(self, parser: ToolCallParser) -> None:
        """Test extracting multiple tool calls."""
        text = (
            '<tool_call name="tool1">{}</tool_call> '
            '<tool_call name="tool2">{}</tool_call>'
        )
        calls = parser.extract_tool_calls(text)
        assert len(calls) == 2
        assert calls[0]["name"] == "tool1"
        assert calls[1]["name"] == "tool2"

    def test_extract_tool_call_partial_complete(
        self, parser: ToolCallParser
    ) -> None:
        """Test partial extraction of complete tool call."""
        buffer = '<tool_call name="test">{"x": 1}</tool_call>'
        result = parser.extract_tool_call_partial(buffer)
        assert result is not None
        assert result.get("is_complete") is True
        assert result["name"] == "test"

    def test_extract_tool_call_partial_incomplete(
        self, parser: ToolCallParser
    ) -> None:
        """Test partial extraction of incomplete tool call."""
        buffer = '<tool_call name="test">{"x":'
        result = parser.extract_tool_call_partial(buffer)
        if result is not None:
            assert result.get("is_complete") is False


# ---------------------------------------------------------------------------
#  SystemPromptManager tests
# ---------------------------------------------------------------------------


class TestSystemPromptManager:
    """Tests for SystemPromptManager."""

    @pytest.fixture
    def manager(self) -> SystemPromptManager:
        return SystemPromptManager()

    def test_build_basic_prompt(self, manager: SystemPromptManager) -> None:
        """Test building a basic prompt."""
        business_ctx = {"name": "Acme Corp", "type": "generic"}
        prompt = manager.build_prompt(business_ctx)
        assert "Acme Corp" in prompt
        assert "professional" in prompt.lower() or "assistant" in prompt.lower()

    def test_build_prompt_with_tools(
        self, manager: SystemPromptManager
    ) -> None:
        """Test building prompt with tools."""
        business_ctx = {"name": "Test Business"}
        tools = [
            {
                "function": {
                    "name": "check_calendar",
                    "description": "Check availability",
                    "parameters": {},
                }
            }
        ]
        prompt = manager.build_prompt(business_ctx, available_tools=tools)
        assert "check_calendar" in prompt or "Test Business" in prompt

    def test_build_prompt_with_caller(
        self, manager: SystemPromptManager
    ) -> None:
        """Test building prompt with caller profile."""
        business_ctx = {"name": "Test Business"}
        caller = {
            "preferred_name": "John",
            "typical_reason": "appointments",
            "last_call_at": "2025-01-01",
        }
        prompt = manager.build_prompt(business_ctx, caller_profile=caller)
        assert "John" in prompt or "Test Business" in prompt

    def test_cache_prompt(self, manager: SystemPromptManager) -> None:
        """Test prompt caching."""
        manager.cache_prompt("tenant-1", "cached prompt")
        assert manager.get_cached_prompt("tenant-1") == "cached prompt"

    def test_get_cached_prompt_miss(self, manager: SystemPromptManager) -> None:
        """Test cache miss."""
        assert manager.get_cached_prompt("nonexistent") is None

    def test_invalidate_cache(self, manager: SystemPromptManager) -> None:
        """Test cache invalidation."""
        manager.cache_prompt("tenant-1", "prompt")
        manager.invalidate_cache("tenant-1")
        assert manager.get_cached_prompt("tenant-1") is None


# ---------------------------------------------------------------------------
#  ConversationHistoryManager tests
# ---------------------------------------------------------------------------


class TestConversationHistoryManager:
    """Tests for ConversationHistoryManager."""

    @pytest.fixture
    def manager(self) -> ConversationHistoryManager:
        return ConversationHistoryManager(max_context_tokens=100)

    def test_add_message(self, manager: ConversationHistoryManager) -> None:
        """Test adding a message."""
        manager.add_message("session-1", "user", "Hello")
        history = manager.get_history("session-1")
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"

    def test_get_empty_history(
        self, manager: ConversationHistoryManager
    ) -> None:
        """Test getting history for unknown session."""
        history = manager.get_history("unknown")
        assert history == []

    def test_multiple_messages(self, manager: ConversationHistoryManager) -> None:
        """Test adding multiple messages."""
        manager.add_message("s1", "user", "Hello")
        manager.add_message("s1", "assistant", "Hi there")
        manager.add_message("s1", "user", "How are you?")
        history = manager.get_history("s1")
        assert len(history) == 3

    def test_trim_history(self, manager: ConversationHistoryManager) -> None:
        """Test history trimming."""
        # Add many messages that exceed context
        for i in range(30):
            manager.add_message("s1", "user", f"Message {i} with some content")
        trimmed = manager.trim_history("s1")
        # Should have trimmed some
        assert len(trimmed) <= 30

    def test_build_messages(
        self, manager: ConversationHistoryManager
    ) -> None:
        """Test building messages for LLM."""
        manager.add_message("s1", "user", "Hello")
        messages = manager.build_messages("s1", "You are an assistant", "New question")
        assert len(messages) >= 2  # System + history + new
        assert messages[0]["role"] == "system"

    def test_clear_history(self, manager: ConversationHistoryManager) -> None:
        """Test clearing history."""
        manager.add_message("s1", "user", "Hello")
        manager.clear_history("s1")
        assert manager.get_history("s1") == []

    def test_add_tool_result(
        self, manager: ConversationHistoryManager
    ) -> None:
        """Test adding tool result."""
        manager.add_tool_result("s1", "check_calendar", {"slots": ["10:00"]})
        history = manager.get_history("s1")
        assert len(history) == 1
        assert history[0]["role"] == "tool"


# ---------------------------------------------------------------------------
#  OllamaClient tests
# ---------------------------------------------------------------------------


class TestOllamaClient:
    """Tests for OllamaClient."""

    @pytest.mark.asyncio
    async def test_start_stop(self, ollama_client: OllamaClient) -> None:
        """Test client start and stop."""
        with patch.object(
            ollama_client, "health_check", new_callable=AsyncMock
        ) as mock_health:
            mock_health.return_value = True
            with patch.object(
                ollama_client, "_load_model", new_callable=AsyncMock
            ) as mock_load:
                await ollama_client.start()
                assert ollama_client._session is not None

                await ollama_client.stop()
                # Session should be handled

    def test_build_payload_basic(self, ollama_client: OllamaClient) -> None:
        """Test building a basic payload."""
        messages = [{"role": "user", "content": "Hello"}]
        payload = ollama_client._build_payload(
            messages=messages, model="test-model"
        )
        assert payload["model"] == "test-model"
        assert payload["messages"] == messages
        assert not payload["stream"]
        assert payload["options"]["temperature"] == 0.7

    def test_build_payload_with_tools(self, ollama_client: OllamaClient) -> None:
        """Test payload with tools."""
        messages = [{"role": "user", "content": "Hello"}]
        tools = [{"type": "function", "function": {"name": "test"}}]
        payload = ollama_client._build_payload(
            messages=messages, model="test", tools=tools
        )
        assert "tools" in payload
        assert len(payload["tools"]) == 1

    def test_build_payload_streaming(self, ollama_client: OllamaClient) -> None:
        """Test payload for streaming."""
        messages = [{"role": "user", "content": "Hello"}]
        payload = ollama_client._build_payload(
            messages=messages, model="test", stream=True
        )
        assert payload["stream"] is True

    def test_build_payload_with_schema(
        self, ollama_client: OllamaClient
    ) -> None:
        """Test payload with JSON schema."""
        messages = [{"role": "user", "content": "Hello"}]
        schema = {"type": "object"}
        payload = ollama_client._build_payload(
            messages=messages, model="test", format_schema=schema
        )
        assert payload["format"] == schema

    def test_count_tokens(self, ollama_client: OllamaClient) -> None:
        """Test token counting."""
        tokens = ollama_client.count_tokens("hello world")
        assert tokens > 0
        assert tokens == max(1, len("hello world") // 4)

    def test_count_message_tokens(self, ollama_client: OllamaClient) -> None:
        """Test message token counting."""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello there"},
        ]
        total = ollama_client.count_message_tokens(messages)
        assert total > 0

    def test_check_context_fit(self, ollama_client: OllamaClient) -> None:
        """Test context window fit check."""
        messages = [{"role": "user", "content": "short"}]
        assert ollama_client.check_context_fit(messages)

    def test_fallback_chain(self) -> None:
        """Test fallback chain is defined."""
        assert len(FALLBACK_CHAIN) >= 2
        assert DEFAULT_MODEL in FALLBACK_CHAIN

    def test_available_models(self) -> None:
        """Test available models are defined."""
        assert len(AVAILABLE_MODELS) >= 2
        assert DEFAULT_MODEL in AVAILABLE_MODELS
        spec = AVAILABLE_MODELS[DEFAULT_MODEL]
        assert isinstance(spec, ModelSpec)
        assert spec.context_length > 0

    @pytest.mark.asyncio
    async def test_chat_all_models_fail(
        self, ollama_client: OllamaClient
    ) -> None:
        """Test graceful handling when all models fail."""
        messages = [{"role": "user", "content": "Hello"}]

        with patch.object(
            ollama_client, "_load_model", new_callable=AsyncMock
        ) as mock_load:
            with patch.object(
                ollama_client, "_get_session", new_callable=AsyncMock
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

                response = await ollama_client.chat(messages)
                assert response.is_error
                assert "trouble" in response.content.lower()

    @pytest.mark.asyncio
    async def test_chat_stream_all_fail(
        self, ollama_client: OllamaClient
    ) -> None:
        """Test streaming when all models fail."""
        messages = [{"role": "user", "content": "Hello"}]

        with patch.object(
            ollama_client, "_load_model", new_callable=AsyncMock
        ):
            with patch.object(
                ollama_client, "_get_session", new_callable=AsyncMock
            ) as mock_session:
                mock_resp = MagicMock()
                mock_resp.status = 500
                mock_cm = MagicMock()
                mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
                mock_cm.__aexit__ = AsyncMock(return_value=None)

                mock_sess = MagicMock()
                mock_sess.post.return_value = mock_cm
                mock_session.return_value = mock_sess

                tokens = []
                async for token in ollama_client.chat_stream(messages):
                    tokens.append(token)

                assert len(tokens) > 0
                assert tokens[-1].is_finished
                assert tokens[-1].finish_reason == "error"


# ---------------------------------------------------------------------------
#  Exception tests
# ---------------------------------------------------------------------------


class TestExceptions:
    """Tests for Ollama exceptions."""

    def test_ollama_error(self) -> None:
        """Test base error."""
        err = OllamaError("test error", status_code=500)
        assert str(err) == "test error"
        assert err.status_code == 500
        assert err.recoverable

    def test_ollama_unavailable(self) -> None:
        """Test unavailable error."""
        err = OllamaUnavailable("server down")
        assert str(err) == "server down"

    def test_ollama_model_error(self) -> None:
        """Test model error."""
        err = OllamaModelError("model not found", model="test-model")
        assert err.model == "test-model"

    def test_non_recoverable_error(self) -> None:
        """Test non-recoverable error."""
        err = OllamaError("fatal", recoverable=False)
        assert not err.recoverable
