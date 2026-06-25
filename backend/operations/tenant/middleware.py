"""operations/tenant/middleware.py - Tenant resolution middleware.

Provides tenant resolution from multiple sources (subdomain, header, JWT)
and validation middleware for the FastAPI application.
"""

from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable, Optional

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from operations.tenant.manager import (
    PlanTier,
    TenantContext,
    TenantManager,
    TenantStatus,
)

logger = structlog.get_logger(__name__)


class TenantResolutionMiddleware(BaseHTTPMiddleware):
    """Resolve tenant from subdomain, header, or JWT claim.

    Resolution order:
        1. X-Tenant-ID header
        2. Subdomain (acme.owlbell.xyz -> acme)
        3. JWT token 'tid' claim
        4. Default tenant (for public routes)
    """

    def __init__(
        self,
        app: ASGIApp,
        tenant_manager: TenantManager,
        default_tenant_id: Optional[str] = None,
        domain_suffix: str = "owlbell.xyz",
    ):
        super().__init__(app)
        self.tenant_manager = tenant_manager
        self.default_tenant_id = (
            uuid.UUID(default_tenant_id) if default_tenant_id else None
        )
        self.domain_suffix = domain_suffix

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        tenant = await self._resolve_tenant(request)
        request.state.tenant = tenant
        request.state.tenant_id = tenant.tenant_id
        request.state.tenant_ctx = tenant

        # Log tenant resolution
        logger.debug(
            "tenant.resolved",
            tenant_id=str(tenant.tenant_id),
            slug=tenant.slug,
            source=getattr(request.state, "tenant_source", "unknown"),
        )

        return await call_next(request)

    async def _resolve_tenant(self, request: Request) -> TenantContext:
        """Resolve tenant from multiple sources."""
        # 1. Check X-Tenant-ID header
        tenant_header = request.headers.get("X-Tenant-ID")
        if tenant_header:
            try:
                tenant_id = uuid.UUID(tenant_header)
                ctx = await self.tenant_manager.get_tenant(tenant_id)
                if ctx:
                    request.state.tenant_source = "header"
                    return ctx
            except (ValueError, Exception):
                logger.debug("Invalid X-Tenant-ID header", header=tenant_header)

        # 2. Check subdomain
        host = request.headers.get("host", "")
        subdomain = self._extract_subdomain(host)
        if subdomain:
            ctx = await self.tenant_manager.get_tenant_by_subdomain(subdomain)
            if ctx:
                request.state.tenant_source = "subdomain"
                return ctx

        # 3. Check JWT claim (set by AuthMiddleware)
        jwt_tenant_id = getattr(request.state, "jwt_tenant_id", None)
        if jwt_tenant_id:
            try:
                if isinstance(jwt_tenant_id, str):
                    jwt_tenant_id = uuid.UUID(jwt_tenant_id)
                ctx = await self.tenant_manager.get_tenant(jwt_tenant_id)
                if ctx:
                    request.state.tenant_source = "jwt"
                    return ctx
            except Exception:
                pass

        # 4. Default tenant
        if self.default_tenant_id:
            try:
                ctx = await self.tenant_manager.get_tenant(self.default_tenant_id)
                if ctx:
                    request.state.tenant_source = "default"
                    return ctx
            except Exception:
                pass

        # 5. Fallback public context
        request.state.tenant_source = "public"
        return self._public_context()

    def _extract_subdomain(self, host: str) -> Optional[str]:
        """Extract subdomain from host header."""
        host = host.split(":")[0]
        suffix = f".{self.domain_suffix}"
        if host.endswith(suffix):
            subdomain = host[: -len(suffix)]
            if subdomain and "." not in subdomain:
                return subdomain
        return None

    def _public_context(self) -> TenantContext:
        """Return a public context for unauthenticated routes."""
        return TenantContext(
            tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            slug="public",
            name="Public",
            subdomain="",
            status=TenantStatus.ACTIVE,
            plan_tier=PlanTier.FREE,
            max_calls_monthly=0,
        )


class TenantValidationMiddleware(BaseHTTPMiddleware):
    """Validate tenant status and enforce limits.

    Checks:
        - Tenant is active (not suspended/deleted)
        - Plan is valid
        - Rate limits are within bounds
    """

    def __init__(
        self,
        app: ASGIApp,
        exempt_paths: Optional[set[str]] = None,
    ):
        super().__init__(app)
        self.exempt_paths = exempt_paths or {
            "/health",
            "/docs",
            "/openapi.json",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
        }

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # Skip validation for exempt paths
        if any(path.startswith(ep) for ep in self.exempt_paths):
            return await call_next(request)

        tenant = getattr(request.state, "tenant", None)
        if not isinstance(tenant, TenantContext):
            return await call_next(request)

        # Skip for public tenant
        if tenant.tenant_id == uuid.UUID("00000000-0000-0000-0000-000000000000"):
            return await call_next(request)

        # Check tenant is active
        if not tenant.is_active():
            return Response(
                content='{"success":false,"error":{"message":"Tenant is not active","code":"tenant_inactive"}}',
                status_code=403,
                media_type="application/json",
            )

        # Check call limit (soft limit - warn but don't block)
        if not tenant.is_within_call_limit():
            logger.warning(
                "tenant.call_limit_warning",
                tenant_id=str(tenant.tenant_id),
                used=tenant.calls_used_this_period,
                limit=tenant.max_calls_monthly,
            )

        return await call_next(request)
