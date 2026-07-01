"""
Tests for orchestrator.circuit_breaker module.

Covers:
- CircuitBreaker state transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Context manager usage
- Sync and async APIs
- Failure threshold enforcement
- Recovery timeout behavior
- Singleton registry
"""

from __future__ import annotations

import asyncio
import pytest

from backend.orchestrator.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    _CIRCUIT_BREAKERS,
    get_circuit_breaker,
    reset_all_circuits,
)


@pytest.fixture(autouse=True)
def reset_circuits():
    """Reset all circuit breakers before each test."""
    reset_all_circuits()
    yield
    reset_all_circuits()


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state(self) -> None:
        """Test that new circuit breaker starts CLOSED."""
        cb = CircuitBreaker(name="test", redis_url="redis://localhost:6379/99")
        assert cb.name == "test"
        assert cb._local_state == CircuitState.CLOSED
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 30

    def test_current_state_sync(self) -> None:
        """Test current_state property (sync)."""
        cb = CircuitBreaker(name="test_st", redis_url="redis://localhost:6379/99")
        state = cb.current_state
        assert state in ("closed", "open", "half_open")

    @pytest.mark.asyncio
    async def test_record_success_closed(self) -> None:
        """Test recording success in CLOSED state resets failures."""
        cb = CircuitBreaker(
            name="test_succ",
            redis_url="redis://localhost:6379/99",
            failure_threshold=3,
        )
        # Manually set some failures
        client = cb._get_sync_client()
        client.hset(cb._key, "state", "closed")
        client.hset(cb._key, "failures", "2")

        await cb.record_success()

        failures = client.hget(cb._key, "failures")
        assert failures == "0" or failures is None

    @pytest.mark.asyncio
    async def test_record_failure_opens_circuit(self) -> None:
        """Test that enough failures opens the circuit."""
        cb = CircuitBreaker(
            name="test_open",
            redis_url="redis://localhost:6379/99",
            failure_threshold=2,
        )
        # Start closed
        client = cb._get_sync_client()
        client.hset(cb._key, "state", "closed")
        client.hset(cb._key, "failures", "0")

        await cb.record_failure()
        await cb.record_failure()

        state = client.hget(cb._key, "state")
        assert state == "open"

    @pytest.mark.asyncio
    async def test_half_open_recovery(self) -> None:
        """Test transition from HALF_OPEN to CLOSED on successes."""
        cb = CircuitBreaker(
            name="test_recover",
            redis_url="redis://localhost:6379/99",
            failure_threshold=2,
            half_open_max_calls=2,
        )
        # Set half-open state
        client = cb._get_sync_client()
        client.hset(cb._key, "state", "half_open")
        client.hset(cb._key, "successes", "0")

        await cb.record_success()
        await cb.record_success()

        state = client.hget(cb._key, "state")
        assert state == "closed"

    @pytest.mark.asyncio
    async def test_async_context_manager_closed(self) -> None:
        """Test async context manager when circuit is CLOSED."""
        cb = CircuitBreaker(
            name="test_ctx",
            redis_url="redis://localhost:6379/99",
        )
        # Ensure closed
        client = cb._get_sync_client()
        client.hset(cb._key, "state", "closed")

        async with cb:
            pass  # Should not raise

    @pytest.mark.asyncio
    async def test_async_context_manager_open_raises(self) -> None:
        """Test that context manager raises when OPEN and not timed out."""
        cb = CircuitBreaker(
            name="test_ctx_open",
            redis_url="redis://localhost:6379/99",
            recovery_timeout=300,  # Long timeout
        )
        # Set open with recent failure
        client = cb._get_sync_client()
        client.hset(cb._key, "state", "open")
        from datetime import datetime
        client.hset(cb._key, "last_failure", datetime.utcnow().isoformat())

        with pytest.raises(CircuitBreakerOpen):
            async with cb:
                pass

    def test_sync_context_manager_closed(self) -> None:
        """Test sync context manager when circuit is CLOSED."""
        cb = CircuitBreaker(
            name="test_sync_ctx",
            redis_url="redis://localhost:6379/99",
        )
        client = cb._get_sync_client()
        client.hset(cb._key, "state", "closed")

        with cb.sync_call():
            pass  # Should not raise

    def test_sync_context_manager_open_raises(self) -> None:
        """Test sync context manager raises when OPEN."""
        cb = CircuitBreaker(
            name="test_sync_ctx_open",
            redis_url="redis://localhost:6379/99",
            recovery_timeout=300,
        )
        client = cb._get_sync_client()
        client.hset(cb._key, "state", "open")
        from datetime import datetime
        client.hset(cb._key, "last_failure", datetime.utcnow().isoformat())

        with pytest.raises(CircuitBreakerOpen):
            with cb.sync_call():
                pass

    def test_sync_success_failure(self) -> None:
        """Test sync success/failure recording."""
        cb = CircuitBreaker(
            name="test_sync_sf",
            redis_url="redis://localhost:6379/99",
            failure_threshold=1,
        )
        client = cb._get_sync_client()
        client.hset(cb._key, "state", "closed")
        client.hset(cb._key, "failures", "0")

        cb.record_sync_success()
        failures = client.hget(cb._key, "failures")
        assert failures == "0"

        cb.record_sync_failure()
        state = client.hget(cb._key, "state")
        assert state == "open"


class TestSingletonRegistry:
    """Tests for circuit breaker singleton registry."""

    def test_get_circuit_breaker_creates_new(self) -> None:
        """Test that get_circuit_breaker creates a new breaker."""
        cb = get_circuit_breaker("new_service")
        assert cb.name == "new_service"
        assert "new_service" in _CIRCUIT_BREAKERS

    def test_get_circuit_breaker_returns_existing(self) -> None:
        """Test that get_circuit_breaker returns existing breaker."""
        cb1 = get_circuit_breaker("existing_service")
        cb2 = get_circuit_breaker("existing_service")
        assert cb1 is cb2

    def test_get_circuit_breaker_different_names(self) -> None:
        """Test that different names create different breakers."""
        cb_llm = get_circuit_breaker("llm")
        cb_stt = get_circuit_breaker("stt")
        cb_tts = get_circuit_breaker("tts")
        assert cb_llm is not cb_stt
        assert cb_stt is not cb_tts
        assert cb_llm.name == "llm"
        assert cb_stt.name == "stt"
        assert cb_tts.name == "tts"

    def test_reset_all_circuits(self) -> None:
        """Test that reset clears all breakers."""
        get_circuit_breaker("service_a")
        get_circuit_breaker("service_b")
        assert len(_CIRCUIT_BREAKERS) >= 2
        reset_all_circuits()
        assert len(_CIRCUIT_BREAKERS) == 0

    def test_get_circuit_breaker_with_custom_threshold(self) -> None:
        """Test creating breaker with custom threshold."""
        cb = get_circuit_breaker(
            "custom_thresh", failure_threshold=10, recovery_timeout=60
        )
        assert cb.failure_threshold == 10
        assert cb.recovery_timeout == 60


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_values(self) -> None:
        """Test state enum values."""
        assert CircuitState.CLOSED == "closed"
        assert CircuitState.OPEN == "open"
        assert CircuitState.HALF_OPEN == "half_open"

    def test_from_string(self) -> None:
        """Test creating state from string."""
        assert CircuitState("closed") == CircuitState.CLOSED
        assert CircuitState("open") == CircuitState.OPEN
        assert CircuitState("half_open") == CircuitState.HALF_OPEN
