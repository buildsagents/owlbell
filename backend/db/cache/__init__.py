"""
Redis caching layer for Owlbell.

Provides ``CacheClient`` for typed cache operations, decorators for
automatic caching, and ``TenantCache`` for multi-tenant scoped keys.
"""

from backend.db.cache.client import (
    CacheClient,
    TenantCache,
    cache_invalidate,
    cached_json,
    close_redis_client,
    get_redis_client,
)

__all__ = [
    "CacheClient",
    "TenantCache",
    "cached_json",
    "cache_invalidate",
    "get_redis_client",
    "close_redis_client",
]
