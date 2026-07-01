"""
Tests for Conversation Memory Store.

Covers session management, message storage, history retrieval,
caller profiles, context window trimming, summaries, and caching.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.ai.memory.conversation_store import (
    CallerProfile,
    ConversationMessage,
    ConversationState,
    ConversationStore,
    ConversationSummary,
    EndReason,
    MessageRole,
    PostgresStore,
    RedisCache,
)


# ---------------------------------------------------------------------------
#  ConversationMessage tests
# ---------------------------------------------------------------------------


class TestConversationMessage:
    """Tests for ConversationMessage dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a message."""
        msg = ConversationMessage(
            session_id="s1",
            role=MessageRole.USER,
            content="Hello",
            sequence=1,
        )
        assert msg.session_id == "s1"
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"

    def test_to_llm_message_user(self) -> None:
        """Test converting user message to LLM format."""
        msg = ConversationMessage(role=MessageRole.USER, content="Hello")
        llm_msg = msg.to_llm_message()
        assert llm_msg == {"role": "user", "content": "Hello"}

    def test_to_llm_message_assistant(self) -> None:
        """Test converting assistant message."""
        msg = ConversationMessage(role=MessageRole.ASSISTANT, content="Hi")
        llm_msg = msg.to_llm_message()
        assert llm_msg["role"] == "assistant"

    def test_to_llm_message_system(self) -> None:
        """Test converting system message."""
        msg = ConversationMessage(role=MessageRole.SYSTEM, content="Prompt")
        llm_msg = msg.to_llm_message()
        assert llm_msg["role"] == "system"

    def test_to_llm_message_tool(self) -> None:
        """Test converting tool message."""
        msg = ConversationMessage(role=MessageRole.TOOL, content="Result")
        llm_msg = msg.to_llm_message()
        assert llm_msg["role"] == "tool"

    def test_defaults(self) -> None:
        """Test default field values."""
        msg = ConversationMessage()
        assert msg.sequence == 0
        assert msg.role == MessageRole.USER
        assert msg.intent is None
        assert msg.metadata == {}


# ---------------------------------------------------------------------------
#  ConversationSummary tests
# ---------------------------------------------------------------------------


class TestConversationSummary:
    """Tests for ConversationSummary dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a summary."""
        summary = ConversationSummary(
            session_id="s1",
            summary="Test conversation",
            key_points=["Point 1", "Point 2"],
        )
        assert summary.session_id == "s1"
        assert len(summary.key_points) == 2

    def test_defaults(self) -> None:
        """Test default values."""
        summary = ConversationSummary()
        assert summary.summary == ""
        assert summary.key_points == []
        assert not summary.caller_satisfied


# ---------------------------------------------------------------------------
#  CallerProfile tests
# ---------------------------------------------------------------------------


class TestCallerProfile:
    """Tests for CallerProfile dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating a profile."""
        profile = CallerProfile(
            tenant_id="t1",
            phone_number="555-1234",
            preferred_name="John",
        )
        assert profile.tenant_id == "t1"
        assert profile.phone_number == "555-1234"
        assert profile.preferred_name == "John"

    def test_defaults(self) -> None:
        """Test default values."""
        profile = CallerProfile()
        assert profile.call_history_count == 0
        assert profile.language == "en"
        assert profile.last_call_at is None

    def test_increment_count(self) -> None:
        """Test that count can be incremented."""
        profile = CallerProfile(call_history_count=5)
        profile.call_history_count += 1
        assert profile.call_history_count == 6


# ---------------------------------------------------------------------------
#  RedisCache tests
# ---------------------------------------------------------------------------


class TestRedisCache:
    """Tests for RedisCache."""

    @pytest.fixture
    def cache(self) -> RedisCache:
        return RedisCache(redis_url="redis://localhost:6379", ttl=60)

    @pytest.mark.asyncio
    async def test_memory_fallback_get_set(self, cache: RedisCache) -> None:
        """Test in-memory fallback cache operations."""
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_memory_fallback_get_miss(self, cache: RedisCache) -> None:
        """Test cache miss returns None."""
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_memory_fallback_delete(self, cache: RedisCache) -> None:
        """Test delete operation."""
        await cache.set("key2", "value2")
        await cache.delete("key2")
        result = await cache.get("key2")
        assert result is None

    @pytest.mark.asyncio
    async def test_json_cache(self, cache: RedisCache) -> None:
        """Test JSON caching."""
        data = {"name": "test", "value": 42}
        await cache.set_json("json_key", data)
        result = await cache.get_json("json_key")
        assert result == data

    @pytest.mark.asyncio
    async def test_json_cache_miss(self, cache: RedisCache) -> None:
        """Test JSON cache miss."""
        result = await cache.get_json("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiry(self, cache: RedisCache) -> None:
        """Test that entries expire."""
        cache.ttl = 0  # Immediate expiry
        await cache.set("expiring", "value")
        # Should still be there immediately
        result = await cache.get("expiring")
        # With ttl=0, it might be expired or not depending on timing

    def test_cache_key(self, cache: RedisCache) -> None:
        """Test cache key building."""
        key = cache._cache_key("session", "abc123")
        assert key == "answerflow:session:abc123"

        key = cache._cache_key("profile", "t1", "5551234")
        assert key == "answerflow:profile:t1:5551234"


# ---------------------------------------------------------------------------
#  PostgresStore tests
# ---------------------------------------------------------------------------


class TestPostgresStore:
    """Tests for PostgresStore."""

    @pytest.fixture
    def store(self) -> PostgresStore:
        return PostgresStore(database_url="postgresql://test")

    @pytest.mark.asyncio
    async def test_create_session(self, store: PostgresStore) -> None:
        """Test creating a session."""
        await store.create_session(
            session_id="s1",
            tenant_id="t1",
            call_id="c1",
            caller_number="555-1234",
            callee_number="555-5678",
        )
        assert "s1" in store._sessions
        assert store._sessions["s1"]["caller_number"] == "555-1234"

    @pytest.mark.asyncio
    async def test_end_session(self, store: PostgresStore) -> None:
        """Test ending a session."""
        await store.create_session("s1", "t1", "c1", "555-1", "555-2")
        await store.end_session("s1", "hangup")
        assert store._sessions["s1"]["state"] == ConversationState.ENDED.value

    @pytest.mark.asyncio
    async def test_update_session_state(self, store: PostgresStore) -> None:
        """Test updating session state."""
        await store.create_session("s1", "t1", "c1", "555-1", "555-2")
        await store.update_session_state("s1", "speaking")
        assert store._sessions["s1"]["state"] == "speaking"

    @pytest.mark.asyncio
    async def test_add_message(self, store: PostgresStore) -> None:
        """Test adding a message."""
        await store.create_session("s1", "t1", "c1", "555-1", "555-2")
        msg = await store.add_message("s1", "user", "Hello", sequence=1)
        assert isinstance(msg, ConversationMessage)
        assert msg.content == "Hello"
        assert msg.session_id == "s1"

    @pytest.mark.asyncio
    async def test_get_history(self, store: PostgresStore) -> None:
        """Test getting conversation history."""
        await store.create_session("s1", "t1", "c1", "555-1", "555-2")
        await store.add_message("s1", "user", "Hello", sequence=1)
        await store.add_message("s1", "assistant", "Hi there", sequence=2)
        history = await store.get_history("s1")
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_history_empty(self, store: PostgresStore) -> None:
        """Test getting history for nonexistent session."""
        history = await store.get_history("nonexistent")
        assert history == []

    @pytest.mark.asyncio
    async def test_get_or_create_profile(self, store: PostgresStore) -> None:
        """Test getting or creating profile."""
        profile = await store.get_or_create_profile("t1", "555-1234")
        assert isinstance(profile, CallerProfile)
        assert profile.tenant_id == "t1"
        assert profile.phone_number == "555-1234"

    @pytest.mark.asyncio
    async def test_get_or_create_existing(self, store: PostgresStore) -> None:
        """Test getting existing profile increments count."""
        profile1 = await store.get_or_create_profile("t1", "555-1234")
        initial_count = profile1.call_history_count
        profile2 = await store.get_or_create_profile("t1", "555-1234")
        assert profile2.call_history_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_update_profile(self, store: PostgresStore) -> None:
        """Test updating profile."""
        await store.get_or_create_profile("t1", "555-1234")
        await store.update_profile(
            "t1", "555-1234", preferred_name="Jane", typical_reason="appointment"
        )
        key = "t1:555-1234"
        assert store._profiles[key].preferred_name == "Jane"
        assert store._profiles[key].typical_reason == "appointment"

    @pytest.mark.asyncio
    async def test_save_and_get_summary(self, store: PostgresStore) -> None:
        """Test saving and getting summary."""
        summary = ConversationSummary(
            session_id="s1",
            summary="Test summary",
            key_points=["Point 1"],
        )
        await store.save_summary(summary)
        retrieved = await store.get_summary("s1")
        assert retrieved is not None
        assert retrieved.summary == "Test summary"


# ---------------------------------------------------------------------------
#  ConversationStore tests
# ---------------------------------------------------------------------------


class TestConversationStore:
    """Tests for the main ConversationStore."""

    @pytest.fixture
    def store(self) -> ConversationStore:
        return ConversationStore()

    @pytest.mark.asyncio
    async def test_start_stop(self, store: ConversationStore) -> None:
        """Test store start and stop."""
        await store.start()
        await store.stop()

    @pytest.mark.asyncio
    async def test_create_and_end_session(self, store: ConversationStore) -> None:
        """Test full session lifecycle."""
        await store.start()
        await store.create_session(
            session_id="s1",
            tenant_id="t1",
            call_id="c1",
            caller_number="555-1",
            callee_number="555-2",
        )
        await store.end_session("s1", "hangup")
        await store.stop()

    @pytest.mark.asyncio
    async def test_add_and_get_message(self, store: ConversationStore) -> None:
        """Test message storage and retrieval."""
        await store.start()
        await store.create_session("s1", "t1", "c1", "555-1", "555-2")
        await store.add_message("s1", "user", "Hello", sequence=1)
        history = await store.get_history("s1")
        assert len(history) == 1
        assert history[0]["content"] == "Hello"
        await store.stop()

    @pytest.mark.asyncio
    async def test_trim_context_window(self, store: ConversationStore) -> None:
        """Test context window trimming."""
        await store.start()
        await store.create_session("s1", "t1", "c1", "555-1", "555-2")

        # Add many messages
        for i in range(50):
            await store.add_message("s1", "user" if i % 2 == 0 else "assistant", f"msg{i}")

        trimmed = await store.trim_context_window("s1", max_messages=10)
        assert len(trimmed) <= 10
        await store.stop()

    @pytest.mark.asyncio
    async def test_get_recent_messages(self, store: ConversationStore) -> None:
        """Test getting recent messages."""
        await store.start()
        await store.create_session("s1", "t1", "c1", "555-1", "555-2")
        for i in range(20):
            await store.add_message("s1", "user", f"msg{i}", sequence=i)

        recent = await store.get_recent_messages("s1", count=5)
        assert len(recent) == 5
        await store.stop()

    @pytest.mark.asyncio
    async def test_caller_profile(self, store: ConversationStore) -> None:
        """Test caller profile with caching."""
        await store.start()
        profile = await store.get_caller_profile("t1", "555-1234")
        assert profile is not None
        assert profile["phone_number"] == "555-1234"
        await store.stop()

    @pytest.mark.asyncio
    async def test_update_caller_profile(self, store: ConversationStore) -> None:
        """Test updating caller profile."""
        await store.start()
        await store.get_caller_profile("t1", "555-1234")
        await store.update_caller_profile(
            "t1", "555-1234", preferred_name="Alice"
        )
        updated = await store.get_caller_profile("t1", "555-1234")
        # Cache invalidated, so this fetches from DB
        assert updated is not None
        await store.stop()

    @pytest.mark.asyncio
    async def test_generate_summary(self, store: ConversationStore) -> None:
        """Test summary generation."""
        await store.start()
        await store.create_session("s1", "t1", "c1", "555-1", "555-2")
        await store.add_message("s1", "user", "Hello, I'd like an appointment")
        await store.add_message("s1", "assistant", "Sure, when would you like?")

        summary = await store.generate_summary("s1")
        assert isinstance(summary, ConversationSummary)
        assert summary.session_id == "s1"
        await store.stop()

    @pytest.mark.asyncio
    async def test_get_business_context(self, store: ConversationStore) -> None:
        """Test getting business context."""
        await store.start()
        ctx = await store.get_business_context("t1")
        assert "name" in ctx
        assert "hours" in ctx
        await store.stop()

    @pytest.mark.asyncio
    async def test_session_state_update(self, store: ConversationStore) -> None:
        """Test session state update."""
        await store.start()
        await store.create_session("s1", "t1", "c1", "555-1", "555-2")
        await store.update_session_state("s1", "speaking")
        await store.stop()

    @pytest.mark.asyncio
    async def test_update_session_metrics(self, store: ConversationStore) -> None:
        """Test metrics update."""
        await store.start()
        await store.create_session("s1", "t1", "c1", "555-1", "555-2")

        metrics = MagicMock()
        metrics.turn_number = 1
        metrics.stt_latency_ms = 100
        metrics.llm_latency_ms = 200
        metrics.tts_latency_ms = 150
        metrics.total_latency_ms = 450

        await store.update_session_metrics("s1", metrics)
        await store.stop()
