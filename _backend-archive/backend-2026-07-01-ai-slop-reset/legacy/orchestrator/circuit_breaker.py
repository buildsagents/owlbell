"""
circuit_breaker.py -- Distributed circuit breaker pattern for AI service calls.

Protects the system from cascading failures when AI services
(STT, LLM, TTS) become slow or unresponsive.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Failure threshold exceeded, requests fail fast
- HALF_OPEN: Testing if service recovered (after timeout)

Uses Redis for distributed state across all workers.

Integration Points:
- IN: AI Pipeline tasks (stt, llm, tts)
- IN: Gateway (HTTP/WebSocket handlers)
- OUT: Redis (circuit breaker state persistence)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import redis.asyncio as aioredis
import redis as sync_redis

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and a call is attempted."""

    pass


class CircuitBreaker:
    """Distributed circuit breaker for external service calls.

    Uses Redis HASH for shared state across processes/workers:
    - ``circuit:{name}`` -> {state, failures, successes, last_failure, opened_at}

    Example:
        cb = get_circuit_breaker("llm")
        async with cb:
            result = await llm_engine.generate(prompt)
    """

    def __init__(
        self,
        name: str,
        redis_client: Optional[Any] = None,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 3,
        redis_url: str = "redis://localhost:6379/0",
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.redis_url = redis_url

        self._async_redis: Optional[aioredis.Redis] = None
        self._sync_redis: Optional[sync_redis.Redis] = None

        if redis_client is not None:
            # Detect async vs sync redis client
            if hasattr(redis_client, "aconnection_pool"):
                self._async_redis = redis_client
            else:
                self._async_redis = redis_client

        self._key = f"circuit:{name}"
        self._local_state = CircuitState.CLOSED
        self._lock = asyncio.Lock()

    def _get_async_client(self) -> aioredis.Redis:
        """Get or create async Redis client."""
        if self._async_redis is None:
            self._async_redis = aioredis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._async_redis

    def _get_sync_client(self) -> sync_redis.Redis:
        """Get or create sync Redis client."""
        if self._sync_redis is None:
            self._sync_redis = sync_redis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._sync_redis

    @property
    def current_state(self) -> str:
        """Get current circuit state (sync, checks Redis).

        This is a synchronous property for use in non-async contexts
        like Celery tasks. It creates a fresh sync Redis connection.
        """
        try:
            client = self._get_sync_client()
            state = client.hget(self._key, "state")
            if state is None:
                return CircuitState.CLOSED.value
            return state
        except Exception:
            return self._local_state.value

    async def acurrent_state(self) -> str:
        """Get current circuit state (async)."""
        try:
            client = self._get_async_client()
            state = await client.hget(self._key, "state")
            if state is None:
                return CircuitState.CLOSED.value
            return state
        except Exception:
            return self._local_state.value

    async def record_success(self) -> None:
        """Record a successful call through the circuit.

        In HALF_OPEN state, counts toward recovery.
        In CLOSED state, resets failure counter.
        """
        async with self._lock:
            client = self._get_async_client()
            state = await client.hget(self._key, "state")

            if state == CircuitState.HALF_OPEN.value:
                successes = int(await client.hincrby(self._key, "successes", 1))
                if successes >= self.half_open_max_calls:
                    await self._close_circuit()
            elif state == CircuitState.CLOSED.value or state is None:
                # Reset failures on success in closed state
                await client.hset(self._key, "failures", "0")

    async def record_failure(self) -> None:
        """Record a failed call through the circuit.

        In CLOSED state, increments failure counter.
        In HALF_OPEN state, immediately re-opens the circuit.
        """
        async with self._lock:
            client = self._get_async_client()
            state = await client.hget(self._key, "state")

            if state in (
                CircuitState.CLOSED.value,
                CircuitState.HALF_OPEN.value,
                None,
            ):
                failures = await client.hincrby(self._key, "failures", 1)
                await client.hset(
                    self._key, "last_failure", datetime.utcnow().isoformat()
                )

                if failures >= self.failure_threshold:
                    await self._open_circuit()

            self._local_state = CircuitState(
                await client.hget(self._key, "state") or "closed"
            )

    @asynccontextmanager
    async def __call__(self):
        """Async context manager for circuit breaker.

        Usage::

            cb = get_circuit_breaker("llm")
            async with cb:
                result = await llm_engine.generate(prompt)
                await cb.record_success()

        Raises:
            CircuitBreakerOpen: If the circuit is OPEN and recovery timeout
                has not yet elapsed.
        """
        state = await self.acurrent_state()

        if state == CircuitState.OPEN.value:
            # Check if recovery timeout has passed
            client = self._get_async_client()
            last_failure_str = await client.hget(self._key, "last_failure")
            if last_failure_str:
                last_failure = datetime.fromisoformat(last_failure_str)
                elapsed = (datetime.utcnow() - last_failure).total_seconds()
                if elapsed >= self.recovery_timeout:
                    await self._half_open_circuit()
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit {self.name} is OPEN "
                        f"(recovery in {self.recovery_timeout - elapsed:.0f}s)"
                    )
            else:
                raise CircuitBreakerOpen(f"Circuit {self.name} is OPEN")

        yield self

    @contextmanager
    def sync_call(self):
        """Synchronous context manager for circuit breaker.

        Usage in Celery tasks::

            cb = get_circuit_breaker("llm")
            with cb.sync_call():
                result = llm_engine.generate(prompt)
                cb.record_sync_success()

        Raises:
            CircuitBreakerOpen: If the circuit is OPEN.
        """
        state = self.current_state

        if state == CircuitState.OPEN.value:
            client = self._get_sync_client()
            last_failure_str = client.hget(self._key, "last_failure")
            if last_failure_str:
                last_failure = datetime.fromisoformat(last_failure_str)
                elapsed = (datetime.utcnow() - last_failure).total_seconds()
                if elapsed >= self.recovery_timeout:
                    # Transition to half-open via sync client
                    client.hset(
                        self._key,
                        mapping={
                            "state": CircuitState.HALF_OPEN.value,
                            "half_open_at": datetime.utcnow().isoformat(),
                            "successes": "0",
                        },
                    )
                    self._local_state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit {self.name} is OPEN "
                        f"(recovery in {self.recovery_timeout - elapsed:.0f}s)"
                    )
            else:
                raise CircuitBreakerOpen(f"Circuit {self.name} is OPEN")

        yield self

    def record_sync_success(self) -> None:
        """Record success from a synchronous context (Celery task)."""
        try:
            client = self._get_sync_client()
            state = client.hget(self._key, "state")

            if state == CircuitState.HALF_OPEN.value:
                successes = int(client.hincrby(self._key, "successes", 1))
                if successes >= self.half_open_max_calls:
                    client.hset(
                        self._key,
                        mapping={
                            "state": CircuitState.CLOSED.value,
                            "closed_at": datetime.utcnow().isoformat(),
                            "failures": "0",
                            "successes": "0",
                        },
                    )
                    self._local_state = CircuitState.CLOSED
                    logger.info(f"Circuit {self.name} CLOSED (recovered)")
            elif state == CircuitState.CLOSED.value or state is None:
                client.hset(self._key, "failures", "0")
        except Exception as exc:
            logger.warning(f"Failed to record sync success: {exc}")

    def record_sync_failure(self) -> None:
        """Record failure from a synchronous context (Celery task)."""
        try:
            client = self._get_sync_client()
            state = client.hget(self._key, "state")

            if state in (CircuitState.CLOSED.value, CircuitState.HALF_OPEN.value, None):
                failures = client.hincrby(self._key, "failures", 1)
                client.hset(self._key, "last_failure", datetime.utcnow().isoformat())

                if failures >= self.failure_threshold:
                    client.hset(
                        self._key,
                        mapping={
                            "state": CircuitState.OPEN.value,
                            "opened_at": datetime.utcnow().isoformat(),
                            "failures": "0",
                            "successes": "0",
                        },
                    )
                    self._local_state = CircuitState.OPEN
                    logger.warning(f"Circuit {self.name} OPENED")
        except Exception as exc:
            logger.warning(f"Failed to record sync failure: {exc}")

    async def _open_circuit(self) -> None:
        """Open the circuit - fail fast mode."""
        client = self._get_async_client()
        await client.hset(
            self._key,
            mapping={
                "state": CircuitState.OPEN.value,
                "opened_at": datetime.utcnow().isoformat(),
                "failures": "0",
                "successes": "0",
            },
        )
        # Record state change in history
        history_key = f"{self._key}:history"
        await client.lpush(
            history_key,
            json.dumps(
                {
                    "state": CircuitState.OPEN.value,
                    "at": datetime.utcnow().isoformat(),
                    "threshold": self.failure_threshold,
                }
            ),
        )
        await client.ltrim(history_key, 0, 99)
        self._local_state = CircuitState.OPEN
        logger.warning(
            f"Circuit {self.name} OPENED (threshold={self.failure_threshold})"
        )

    async def _close_circuit(self) -> None:
        """Close the circuit - normal operation."""
        client = self._get_async_client()
        await client.hset(
            self._key,
            mapping={
                "state": CircuitState.CLOSED.value,
                "closed_at": datetime.utcnow().isoformat(),
                "failures": "0",
                "successes": "0",
            },
        )
        history_key = f"{self._key}:history"
        await client.lpush(
            history_key,
            json.dumps(
                {"state": CircuitState.CLOSED.value, "at": datetime.utcnow().isoformat()}
            ),
        )
        await client.ltrim(history_key, 0, 99)
        self._local_state = CircuitState.CLOSED
        logger.info(f"Circuit {self.name} CLOSED (recovered)")

    async def _half_open_circuit(self) -> None:
        """Transition to half-open state - testing recovery."""
        client = self._get_async_client()
        await client.hset(
            self._key,
            mapping={
                "state": CircuitState.HALF_OPEN.value,
                "half_open_at": datetime.utcnow().isoformat(),
                "successes": "0",
            },
        )
        history_key = f"{self._key}:history"
        await client.lpush(
            history_key,
            json.dumps(
                {
                    "state": CircuitState.HALF_OPEN.value,
                    "at": datetime.utcnow().isoformat(),
                }
            ),
        )
        await client.ltrim(history_key, 0, 99)
        self._local_state = CircuitState.HALF_OPEN
        logger.info(f"Circuit {self.name} HALF-OPEN (testing recovery)")

    async def get_history(self, limit: int = 100) -> list:
        """Get circuit breaker state change history."""
        client = self._get_async_client()
        entries = await client.lrange(f"{self._key}:history", 0, limit - 1)
        return [json.loads(e) for e in entries if e]

    async def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED."""
        await self._close_circuit()
        logger.info(f"Circuit {self.name} manually reset")


# Singleton circuit breakers registry
_CIRCUIT_BREAKERS: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    redis_url: str = "redis://localhost:6379/0",
    failure_threshold: int = 5,
    recovery_timeout: int = 30,
    half_open_max_calls: int = 3,
) -> CircuitBreaker:
    """Get or create a circuit breaker by name.

    Args:
        name: Circuit breaker name (e.g., "llm", "stt", "tts")
        redis_url: Redis connection URL
        failure_threshold: Number of failures before opening
        recovery_timeout: Seconds to wait before testing recovery
        half_open_max_calls: Successful calls needed to close circuit

    Returns:
        CircuitBreaker instance
    """
    if name not in _CIRCUIT_BREAKERS:
        _CIRCUIT_BREAKERS[name] = CircuitBreaker(
            name=name,
            redis_url=redis_url,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
        )
    return _CIRCUIT_BREAKERS[name]


def reset_all_circuits() -> None:
    """Reset all circuit breakers (for testing/emergencies)."""
    _CIRCUIT_BREAKERS.clear()
    logger.info("All circuit breakers reset")


async def reset_all_circuits_async() -> None:
    """Async reset all circuit breakers and their Redis state."""
    for name, cb in list(_CIRCUIT_BREAKERS.items()):
        try:
            await cb.reset()
        except Exception as exc:
            logger.warning(f"Failed to reset circuit {name}: {exc}")
    _CIRCUIT_BREAKERS.clear()
    logger.info("All circuit breakers reset (async)")
