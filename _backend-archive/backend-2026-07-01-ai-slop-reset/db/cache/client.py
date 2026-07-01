"""
Redis cache client with JSON serialization, decorators, and tenant scoping.

Location: backend/db/cache/client.py

Provides:
- ``CacheClient``: High-level async cache with typed operations
- ``@cached_json``: Decorator for automatic JSON response caching
- ``@cache_invalidate``: Decorator to invalidate cache patterns
- ``TenantCache``: Scoped cache keys for multi-tenant isolation

Dependencies (zero-budget / open-source):
- ``redis-py`` (BSD-3) — async Redis client
"""

from __future__ import annotations

import functools
import hashlib
import json
import pickle
from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
    TypeVar,
)
from uuid import UUID

import redis.asyncio as redis_lib
from redis.asyncio import Redis

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Awaitable[Any]])

# ── Singleton Redis Client ──────────────────────────────────────

_redis_client: Optional[Redis] = None


def _get_redis_url() -> str:
    """Get Redis URL from environment variables.

    Falls back to localhost defaults for development.
    """
    import os

    host = os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")
    password = os.getenv("REDIS_PASSWORD", "")
    user = os.getenv("REDIS_USER", "")

    if password:
        creds = f"{user}:{password}@" if user else f"{password}@"
        return f"redis://{creds}{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


async def get_redis_client() -> Redis:
    """Get or create the shared async Redis client (singleton).

    When the ``USE_FAKE_REDIS`` environment variable is truthy, an in-process
    ``fakeredis`` server is used instead of a real Redis connection. This lets
    the application boot locally with zero external infrastructure.

    Returns:
        An async Redis client instance.
    """
    global _redis_client
    if _redis_client is None:
        import os

        if os.getenv("USE_FAKE_REDIS", "").lower() in ("1", "true", "yes"):
            import fakeredis.aioredis

            _redis_client = fakeredis.aioredis.FakeRedis(
                encoding="utf-8",
                decode_responses=True,
            )
        else:
            _redis_client = redis_lib.from_url(
                _get_redis_url(),
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,
                socket_keepalive=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
    return _redis_client


async def close_redis_client() -> None:
    """Close the shared Redis connection pool.

    Call this during application shutdown for clean resource cleanup.
    """
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


# ── Cache Client ────────────────────────────────────────────────


class CacheClient:
    """High-level async cache client with typed operations.

    Wraps a ``Redis`` client with JSON/object serialization,
    namespace management, and safe key patterns.

    Args:
        redis_client: An async ``Redis`` instance.
    """

    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    # ── String Operations ─────────────────────────────────────────

    async def get(self, key: str) -> Optional[str]:
        """Get a string value by key."""
        return await self._redis.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
    ) -> None:
        """Set a string value with optional TTL (seconds)."""
        await self._redis.set(key, value, ex=ttl)

    async def delete(self, key: str) -> int:
        """Delete a key. Returns number of keys deleted."""
        return await self._redis.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        .. warning::
            Uses ``KEYS`` internally. Use sparingly in production —
            prefer ``SCAN`` for large keyspaces.
        """
        keys = await self._redis.keys(pattern)
        if keys:
            return await self._redis.delete(*keys)
        return 0

    # ── JSON Operations ───────────────────────────────────────────

    async def get_json(self, key: str) -> Optional[dict]:
        """Get and parse a JSON value."""
        raw = await self._redis.get(key)
        if raw is None:
            return None
        if isinstance(raw, str):
            return json.loads(raw)
        return json.loads(raw.decode("utf-8"))

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Serialize and store a JSON-serializable value."""
        await self._redis.set(key, json.dumps(value), ex=ttl)

    # ── Object Operations (pickle) ────────────────────────────────

    async def get_object(self, key: str) -> Optional[Any]:
        """Get a pickled object."""
        raw = await self._redis.get(key)
        if raw is None:
            return None
        if isinstance(raw, str):
            raw = raw.encode("latin-1")
        return pickle.loads(raw)

    async def set_object(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Pickle and store an arbitrary Python object."""
        pickled = pickle.dumps(value)
        await self._redis.set(key, pickled, ex=ttl)

    # ── List Operations ───────────────────────────────────────────

    async def push_list(
        self, key: str, value: str, ttl: Optional[int] = None
    ) -> None:
        """Push a value onto a list."""
        await self._redis.lpush(key, value)
        if ttl:
            await self._redis.expire(key, ttl)

    async def get_list(
        self, key: str, start: int = 0, end: int = -1
    ) -> list[str]:
        """Get a range from a list."""
        result = await self._redis.lrange(key, start, end)
        return result if result else []

    # ── Hash Operations ───────────────────────────────────────────

    async def hget(self, key: str, field: str) -> Optional[str]:
        """Get a hash field value."""
        return await self._redis.hget(key, field)

    async def hset(
        self, key: str, field: str, value: str
    ) -> None:
        """Set a hash field value."""
        await self._redis.hset(key, field, value)

    async def hgetall(self, key: str) -> dict[str, str]:
        """Get all fields and values from a hash."""
        result = await self._redis.hgetall(key)
        return result if result else {}

    # ── Utility ───────────────────────────────────────────────────

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        return await self._redis.exists(key) > 0

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for a key (seconds, -1 = no TTL, -2 = missing)."""
        return await self._redis.ttl(key)

    async def incr(self, key: str) -> int:
        """Increment a counter."""
        return await self._redis.incr(key)

    async def expire(self, key: str, seconds: int) -> None:
        """Set expiration on a key."""
        await self._redis.expire(key, seconds)

    async def flush_namespace(self, namespace: str) -> int:
        """Delete all keys in a namespace.

        Args:
            namespace: Key prefix, e.g. ``"faq:tenant-uuid:"``.

        Returns:
            Number of keys deleted.
        """
        pattern = f"{namespace}*"
        return await self.delete_pattern(pattern)

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: Optional[int] = None,
        serializer: str = "json",
    ) -> T:
        """Get from cache or compute and store.

        Implements the cache-aside pattern: checks the cache first,
        and if missing, calls ``factory`` to compute the value,
        stores it, and returns it.

        Args:
            key: Cache key.
            factory: Async callable that produces the value.
            ttl: Time-to-live in seconds.
            serializer: ``"json"`` or ``"pickle"``.

        Returns:
            The cached or computed value.
        """
        if serializer == "json":
            cached = await self.get_json(key)
            if cached is not None:
                return cached  # type: ignore[return-value]
            value = await factory()
            await self.set_json(key, value, ttl=ttl)
            return value  # type: ignore[return-value]

        # pickle fallback
        cached = await self.get_object(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        value = await factory()
        await self.set_object(key, value, ttl=ttl)
        return value  # type: ignore[return-value]


# ── Decorators ──────────────────────────────────────────────────


def _generate_key(
    prefix: str, func_name: str, args: tuple, kwargs: dict
) -> str:
    """Generate a deterministic cache key from function arguments."""
    key_parts = [prefix, func_name]
    for arg in args:
        key_parts.append(str(arg))
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={v}")
    raw_key = ":".join(key_parts)
    # Hash if too long
    if len(raw_key) > 200:
        return f"{prefix}:{func_name}:{hashlib.md5(raw_key.encode()).hexdigest()}"
    return raw_key


def cached_json(
    ttl: int = 300,
    key_prefix: str = "cache",
    key_builder: Optional[Callable] = None,
    skip_args: Optional[list[int]] = None,
) -> Callable[[F], F]:
    """Decorator that caches function result as JSON.

    Args:
        ttl: Time-to-live in seconds.
        key_prefix: Prefix for cache key.
        key_builder: Optional custom key builder function.
        skip_args: Argument indices to exclude from cache key
            (e.g. ``[0]`` to skip a session object).

    Example::

        @cached_json(ttl=300, key_prefix="tenant")
        async def get_tenant_config(tenant_id: UUID) -> dict:
            # ... expensive database query
            return config
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                filtered_args = args
                if skip_args:
                    filtered_args = tuple(
                        v for i, v in enumerate(args) if i not in skip_args
                    )
                cache_key = _generate_key(
                    key_prefix, func.__qualname__, filtered_args, kwargs
                )

            # Try cache
            redis_client = await get_redis_client()
            cache = CacheClient(redis_client)
            cached = await cache.get_json(cache_key)
            if cached is not None:
                return cached

            # Execute and cache
            result = await func(*args, **kwargs)
            await cache.set_json(cache_key, result, ttl=ttl)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


def cache_invalidate(
    key_pattern: str,
) -> Callable[[F], F]:
    """Decorator that invalidates cache keys after function execution.

    The pattern can contain ``{argN}`` or ``{kwarg_name}`` placeholders
    that are substituted with actual argument values.

    Example::

        @cache_invalidate("faq:{tenant_id}:*")
        async def update_faq(tenant_id: UUID, ...):
            # ... update FAQ in DB
            pass  # Cache invalidated automatically
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            # Build pattern by substituting positional/keyword args
            pattern = key_pattern
            for i, arg in enumerate(args):
                pattern = pattern.replace(f"{{arg{i}}}", str(arg))
            for k, v in kwargs.items():
                pattern = pattern.replace(f"{{{k}}}", str(v))

            redis_client = await get_redis_client()
            cache = CacheClient(redis_client)
            await cache.delete_pattern(pattern)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


# ── Tenant Cache ────────────────────────────────────────────────


class TenantCache:
    """Cache layer for tenant-specific configuration.

    Provides scoped cache keys and TTL management for tenant data
    that changes infrequently but is accessed on every call:
    tenant config, business hours, FAQ entries, caller profiles, etc.

    Args:
        cache: A ``CacheClient`` instance.
    """

    # TTL Constants (seconds)
    CONFIG_TTL = 300       # 5 minutes
    SLUG_MAP_TTL = 600     # 10 minutes
    HOURS_TTL = 1800       # 30 minutes
    FAQ_TTL = 600          # 10 minutes
    CALLERS_TTL = 600      # 10 minutes
    ROUTING_TTL = 300      # 5 minutes
    ACTIVE_CALLS_TTL = 30  # 30 seconds

    def __init__(self, cache: CacheClient) -> None:
        self._cache = cache

    # ── Key Builders ──────────────────────────────────────────────

    def _config_key(self, tenant_id: UUID) -> str:
        return f"tenant:{tenant_id}:config"

    def _slug_key(self, slug: str) -> str:
        return f"tenant_slug:{slug}"

    def _hours_key(self, tenant_id: UUID) -> str:
        return f"hours:{tenant_id}"

    def _faq_list_key(self, tenant_id: UUID) -> str:
        return f"faq:{tenant_id}:all"

    def _faq_entry_key(self, tenant_id: UUID, entry_id: UUID) -> str:
        return f"faq:{tenant_id}:{entry_id}"

    def _caller_key(self, tenant_id: UUID, phone_hash: str) -> str:
        return f"caller:{tenant_id}:{phone_hash}"

    def _routing_key(self, tenant_id: UUID) -> str:
        return f"routing:{tenant_id}"

    def _active_calls_key(self, tenant_id: UUID) -> str:
        return f"calls:active:{tenant_id}"

    # ── Tenant Config ─────────────────────────────────────────────

    async def get_config(self, tenant_id: UUID) -> Optional[dict]:
        """Get cached tenant configuration."""
        return await self._cache.get_json(self._config_key(tenant_id))

    async def set_config(self, tenant_id: UUID, config: dict) -> None:
        """Cache tenant configuration."""
        await self._cache.set_json(
            self._config_key(tenant_id), config, ttl=self.CONFIG_TTL
        )

    async def invalidate_config(self, tenant_id: UUID) -> int:
        """Invalidate cached tenant configuration."""
        return await self._cache.delete(self._config_key(tenant_id))

    # ── Slug → ID Mapping ─────────────────────────────────────────

    async def get_tenant_id_by_slug(self, slug: str) -> Optional[str]:
        """Get tenant ID from slug cache."""
        return await self._cache.get(self._slug_key(slug))

    async def set_tenant_slug(self, slug: str, tenant_id: UUID) -> None:
        """Cache slug → tenant_id mapping."""
        await self._cache.set(
            self._slug_key(slug), str(tenant_id), ttl=self.SLUG_MAP_TTL
        )

    async def invalidate_slug(self, slug: str) -> int:
        """Invalidate slug cache."""
        return await self._cache.delete(self._slug_key(slug))

    # ── Business Hours ────────────────────────────────────────────

    async def get_hours(self, tenant_id: UUID) -> Optional[dict]:
        """Get cached business hours."""
        return await self._cache.get_json(self._hours_key(tenant_id))

    async def set_hours(self, tenant_id: UUID, hours: dict) -> None:
        """Cache business hours."""
        await self._cache.set_json(
            self._hours_key(tenant_id), hours, ttl=self.HOURS_TTL
        )

    async def invalidate_hours(self, tenant_id: UUID) -> int:
        """Invalidate cached business hours."""
        return await self._cache.delete(self._hours_key(tenant_id))

    # ── FAQ ───────────────────────────────────────────────────────

    async def get_faq_list(self, tenant_id: UUID) -> Optional[list]:
        """Get cached FAQ list for a tenant."""
        return await self._cache.get_json(self._faq_list_key(tenant_id))

    async def set_faq_list(self, tenant_id: UUID, faq_list: list) -> None:
        """Cache FAQ list for a tenant."""
        await self._cache.set_json(
            self._faq_list_key(tenant_id), faq_list, ttl=self.FAQ_TTL
        )

    async def get_faq_entry(
        self, tenant_id: UUID, entry_id: UUID
    ) -> Optional[dict]:
        """Get cached FAQ entry."""
        return await self._cache.get_json(
            self._faq_entry_key(tenant_id, entry_id)
        )

    async def set_faq_entry(
        self, tenant_id: UUID, entry_id: UUID, entry: dict
    ) -> None:
        """Cache a single FAQ entry."""
        await self._cache.set_json(
            self._faq_entry_key(tenant_id, entry_id),
            entry,
            ttl=self.FAQ_TTL,
        )

    async def invalidate_faq(self, tenant_id: UUID) -> int:
        """Invalidate all cached FAQ data for a tenant."""
        return await self._cache.flush_namespace(f"faq:{tenant_id}:")

    # ── Caller Profiles ───────────────────────────────────────────

    async def get_caller(
        self, tenant_id: UUID, phone_hash: str
    ) -> Optional[dict]:
        """Get cached caller profile."""
        return await self._cache.get_json(
            self._caller_key(tenant_id, phone_hash)
        )

    async def set_caller(
        self, tenant_id: UUID, phone_hash: str, profile: dict
    ) -> None:
        """Cache a caller profile."""
        await self._cache.set_json(
            self._caller_key(tenant_id, phone_hash),
            profile,
            ttl=self.CALLERS_TTL,
        )

    async def invalidate_caller(
        self, tenant_id: UUID, phone_hash: str
    ) -> int:
        """Invalidate cached caller profile."""
        return await self._cache.delete(
            self._caller_key(tenant_id, phone_hash)
        )

    # ── Routing Rules ─────────────────────────────────────────────

    async def get_routing(self, tenant_id: UUID) -> Optional[list]:
        """Get cached routing rules for a tenant."""
        return await self._cache.get_json(self._routing_key(tenant_id))

    async def set_routing(
        self, tenant_id: UUID, rules: list
    ) -> None:
        """Cache routing rules for a tenant."""
        await self._cache.set_json(
            self._routing_key(tenant_id), rules, ttl=self.ROUTING_TTL
        )

    async def invalidate_routing(self, tenant_id: UUID) -> int:
        """Invalidate cached routing rules."""
        return await self._cache.delete(self._routing_key(tenant_id))

    # ── Active Calls ──────────────────────────────────────────────

    async def get_active_calls(self, tenant_id: UUID) -> Optional[list]:
        """Get cached active calls for a tenant."""
        return await self._cache.get_json(
            self._active_calls_key(tenant_id)
        )

    async def set_active_calls(
        self, tenant_id: UUID, calls: list
    ) -> None:
        """Cache active calls for a tenant."""
        await self._cache.set_json(
            self._active_calls_key(tenant_id),
            calls,
            ttl=self.ACTIVE_CALLS_TTL,
        )

    # ── Bulk Invalidation ─────────────────────────────────────────

    async def invalidate_all(self, tenant_id: UUID) -> int:
        """Invalidate all cached data for a tenant.

        Call this when a tenant's configuration is updated to ensure
        stale data is not served.

        Returns:
            Total number of keys invalidated.
        """
        total = 0
        total += await self.invalidate_config(tenant_id)
        total += await self.invalidate_hours(tenant_id)
        total += await self.invalidate_faq(tenant_id)
        total += await self.invalidate_routing(tenant_id)
        # Active calls and callers are transient — skip bulk clear
        return total
