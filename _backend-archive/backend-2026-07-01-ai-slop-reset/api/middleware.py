"""api/middleware.py - FastAPI middleware chain for Owlbell.

Includes:
    - TenantMiddleware: resolve tenant from subdomain/JWT
    - AuthMiddleware: JWT validation
    - RateLimitMiddleware: sliding window per tenant
    - LoggingMiddleware: request logging with structlog
    - TimingMiddleware: request timing headers
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Optional

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Tenant Resolution Middleware
# ---------------------------------------------------------------------------


class TenantContext:
    """Lightweight tenant context attached to request.state."""

    def __init__(
        self,
        tenant_id: uuid.UUID,
        name: str,
        slug: str,
        subdomain: str,
        plan: str = "free",
        status: str = "active",
        timezone: str = "America/New_York",
        max_calls_monthly: int = 100,
        calls_used_this_period: int = 0,
    ):
        self.tenant_id = tenant_id
        self.name = name
        self.slug = slug
        self.subdomain = subdomain
        self.plan = plan
        self.status = status
        self.timezone = timezone
        self.max_calls_monthly = max_calls_monthly
        self.calls_used_this_period = calls_used_this_period

    def is_active(self) -> bool:
        return self.status in ("active", "limited")

    def is_within_call_limit(self) -> bool:
        return self.calls_used_this_period < self.max_calls_monthly

    def to_log_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "slug": self.slug,
            "status": self.status,
            "plan": self.plan,
            "usage_calls": self.calls_used_this_period,
        }


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve tenant from subdomain, header, or JWT claim.

    Resolution order:
        1. JWT tid (decode Bearer directly)
        2. Subdomain (acme.owlbell.xyz -> acme)
        3. X-Tenant-ID header (only if matches JWT tid)
        4. Default tenant
        5. Public fallback
    """

    def __init__(
        self,
        app: ASGIApp,
        default_tenant_id: Optional[str] = None,
        domain_suffix: str = "owlbell.xyz",
    ):
        super().__init__(app)
        self.default_tenant_id = default_tenant_id
        self.domain_suffix = domain_suffix
        self._cache: dict[str, dict[str, Any]] = {}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        tenant = await self._resolve_tenant(request)
        request.state.tenant = tenant
        request.state.tenant_id = tenant.tenant_id
        return await call_next(request)

    async def _resolve_tenant(self, request: Request) -> TenantContext:
        """Resolve tenant from multiple sources."""
        from api.tenant_lookup import tenant_id_from_jwt_header

        jwt_tid = tenant_id_from_jwt_header(request)

        # 1. JWT tid (decode Bearer directly)
        if jwt_tid:
            ctx = await self._lookup_tenant(jwt_tid)
            if ctx:
                return ctx

        # 2. Subdomain
        host = request.headers.get("host", "")
        subdomain = self._extract_subdomain(host)
        if subdomain:
            ctx = await self._lookup_tenant_by_subdomain(subdomain)
            if ctx:
                return ctx

        # 3. X-Tenant-ID header only when it matches JWT tid (reject spoofing)
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header and jwt_tid:
            try:
                header_tid = uuid.UUID(tenant_header)
                if header_tid == jwt_tid:
                    ctx = await self._lookup_tenant(header_tid)
                    if ctx:
                        return ctx
            except ValueError:
                logger.warning("Invalid X-Tenant-ID header", header=tenant_header)

        # 4. Default tenant
        if self.default_tenant_id:
            ctx = await self._lookup_tenant(uuid.UUID(self.default_tenant_id))
            if ctx:
                return ctx

        # 5. Public fallback
        return self._fallback_context()

    def _extract_subdomain(self, host: str) -> Optional[str]:
        """Extract subdomain from host header."""
        host = host.split(":")[0]  # Strip port
        if host.endswith(f".{self.domain_suffix}"):
            subdomain = host[: -len(self.domain_suffix) - 1]
            if subdomain and "." not in subdomain:
                return subdomain
        return None

    async def _lookup_tenant(self, tenant_id: uuid.UUID) -> Optional[TenantContext]:
        """Look up tenant by ID via PostgreSQL, with in-memory cache."""
        cache_key = f"tenant:id:{tenant_id}"
        if cache_key in self._cache:
            data = self._cache[cache_key]
            return TenantContext(**data)

        from api.tenant_lookup import lookup_tenant_by_id
        from backend.db.session import open_db_session

        async with open_db_session() as session:
            data = await lookup_tenant_by_id(session, tenant_id)

        if not data:
            return None

        self._cache[cache_key] = data
        self._cache[f"tenant:sub:{data['slug']}"] = data
        return TenantContext(**data)

    async def _lookup_tenant_by_subdomain(
        self, subdomain: str
    ) -> Optional[TenantContext]:
        """Look up tenant by subdomain slug via PostgreSQL."""
        cache_key = f"tenant:sub:{subdomain}"
        if cache_key in self._cache:
            data = self._cache[cache_key]
            return TenantContext(**data)

        from api.tenant_lookup import lookup_tenant_by_slug
        from backend.db.session import open_db_session

        async with open_db_session() as session:
            data = await lookup_tenant_by_slug(session, subdomain)

        if not data:
            return None

        self._cache[cache_key] = data
        self._cache[f"tenant:id:{data['tenant_id']}"] = data
        return TenantContext(**data)

    def _fallback_context(self) -> TenantContext:
        """Return a fallback context for unauthenticated/public routes."""
        return TenantContext(
            tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            name="public",
            slug="public",
            subdomain="",
            status="active",
        )


# ---------------------------------------------------------------------------
# Authentication Middleware
# ---------------------------------------------------------------------------


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT validation middleware.

    Validates Bearer token from Authorization header, extracts user context,
    and attaches it to request.state.
    """

    def __init__(
        self,
        app: ASGIApp,
        secret_key: str,
        algorithm: str = "HS256",
        exempt_paths: Optional[set[str]] = None,
    ):
        super().__init__(app)
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.exempt_paths = exempt_paths or {
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/magic-link",
            "/api/v1/auth/verify-email",
            "/health",
            "/docs",
            "/openapi.json",
        }

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # Skip auth for exempt paths
        if any(path.startswith(ep) for ep in self.exempt_paths):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": {"message": "Authentication required", "code": "missing_token"},
                }),
                status_code=401,
                media_type="application/json",
            )

        token = auth_header[7:]
        user_ctx = await self._validate_token(token)
        if not user_ctx:
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": {"message": "Invalid or expired token", "code": "invalid_token"},
                }),
                status_code=401,
                media_type="application/json",
            )

        request.state.user = user_ctx
        request.state.jwt_tenant_id = user_ctx.get("tenant_id")
        return await call_next(request)

    async def _validate_token(self, token: str) -> Optional[dict[str, Any]]:
        """Validate JWT and return user context (shared secret via auth_tokens)."""
        try:
            from api.auth_tokens import decode_token

            payload = decode_token(token)
            if payload.get("type") != "access":
                return None  # refresh tokens are not valid for API access
            return {
                "user_id": payload.get("sub"),
                "tenant_id": payload.get("tid"),
                "role": payload.get("role", "viewer"),
                "email": payload.get("email", ""),
            }
        except Exception:
            logger.debug("Token validation failed")
            return None


# ---------------------------------------------------------------------------
# Rate Limit Middleware
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter per tenant.

    Uses Redis for distributed counter storage.
    Returns 429 when limit exceeded.
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_url: str = "redis://localhost:6379",
        requests_per_minute: int = 100,
        requests_per_hour: int = 5000,
        exempt_paths: Optional[set[str]] = None,
    ):
        super().__init__(app)
        self.redis_url = redis_url
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.exempt_paths = exempt_paths or {
            "/health",
            "/docs",
            "/openapi.json",
        }
        self._local_counters: dict[str, dict[str, Any]] = {}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        if any(path.startswith(ep) for ep in self.exempt_paths):
            return await call_next(request)

        tenant = getattr(request.state, "tenant", None)
        if not tenant or not isinstance(tenant, TenantContext):
            return await call_next(request)

        tenant_id = str(tenant.tenant_id)
        allowed = await self._check_rate_limit(tenant_id)

        if not allowed:
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": {
                        "message": "Rate limit exceeded. Try again later.",
                        "code": "rate_limit_exceeded",
                    },
                }),
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        # Add rate limit headers
        remaining = await self._get_remaining(tenant_id)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        return response

    async def _check_rate_limit(self, tenant_id: str) -> bool:
        """Check if tenant is within rate limit using local sliding window."""
        now = time.time()
        key = f"rl:{tenant_id}"

        if key not in self._local_counters:
            self._local_counters[key] = {"minute_window": [], "hour_window": []}

        counter = self._local_counters[key]
        minute_ago = now - 60
        hour_ago = now - 3600

        # Clean old entries
        counter["minute_window"] = [t for t in counter["minute_window"] if t > minute_ago]
        counter["hour_window"] = [t for t in counter["hour_window"] if t > hour_ago]

        # Check limits
        if len(counter["minute_window"]) >= self.requests_per_minute:
            return False
        if len(counter["hour_window"]) >= self.requests_per_hour:
            return False

        # Record request
        counter["minute_window"].append(now)
        counter["hour_window"].append(now)
        return True

    async def _get_remaining(self, tenant_id: str) -> int:
        """Get remaining requests this minute."""
        key = f"rl:{tenant_id}"
        counter = self._local_counters.get(key, {})
        minute_window = counter.get("minute_window", [])
        return self.requests_per_minute - len(minute_window)


# ---------------------------------------------------------------------------
# Logging Middleware
# ---------------------------------------------------------------------------


class LoggingMiddleware(BaseHTTPMiddleware):
    """Request/response logging with structured logging via structlog.

    Logs every request with timing, method, path, status, tenant, and user.
    """

    def __init__(
        self,
        app: ASGIApp,
        log_level: str = "INFO",
        sensitive_headers: Optional[set[str]] = None,
    ):
        super().__init__(app)
        self.log_level = log_level.upper()
        self.sensitive_headers = sensitive_headers or {
            "authorization",
            "cookie",
            "x-api-key",
        }

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid.uuid4())[:12]
        request.state.request_id = request_id

        start_time = time.perf_counter()

        # Collect request info
        method = request.method
        path = request.url.path
        query = str(request.query_params)
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        tenant = getattr(request.state, "tenant", None)
        tenant_info = tenant.to_log_dict() if tenant else {}

        logger.info(
            "request.started",
            request_id=request_id,
            method=method,
            path=path,
            query=query[:200] if query else None,
            client_ip=client_ip,
            user_agent=user_agent[:200],
            **tenant_info,
        )

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000
            status_code = response.status_code

            log_fn = logger.warning if status_code >= 400 else logger.info
            log_fn(
                "request.completed",
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=round(duration_ms, 2),
                **tenant_info,
            )

            # Attach request ID to response
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "request.failed",
                request_id=request_id,
                method=method,
                path=path,
                duration_ms=round(duration_ms, 2),
                error=str(exc),
                error_type=type(exc).__name__,
                **tenant_info,
            )
            raise

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, respecting proxy headers."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        if request.client:
            return request.client.host
        return "unknown"


# ---------------------------------------------------------------------------
# Timing Middleware
# ---------------------------------------------------------------------------


class TimingMiddleware(BaseHTTPMiddleware):
    """Add request timing headers to all responses.

    Headers added:
        X-Response-Time: Total request processing time in milliseconds
        X-Request-ID: Unique request identifier
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Add cache status hint
        response.headers["X-Cache-Status"] = "MISS"

        return response


# ---------------------------------------------------------------------------
# Error Handler Middleware
# ---------------------------------------------------------------------------


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Catch unhandled exceptions and return standardized error responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:12])
            logger.error(
                "request.unhandled_exception",
                request_id=request_id,
                error=str(exc),
                error_type=type(exc).__name__,
                path=request.url.path,
            )

            error_body = json.dumps({
                "success": False,
                "error": {
                    "message": "An unexpected error occurred",
                    "code": "internal_error",
                },
                "meta": {
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "api_version": "v1",
                },
            })

            return Response(
                content=error_body,
                status_code=500,
                media_type="application/json",
                headers={"X-Request-ID": request_id},
            )
