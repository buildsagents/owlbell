"""api/dependencies.py - FastAPI HTTP dependencies (auth, tenant, DB sessions).

Layer boundaries (do not cross-import):
- ``backend.db.session`` — session factory (``require_session_maker``, ``open_db_session``)
- ``backend.dependencies`` — app services (AI, Redis, usage tracker); **not imported here**
- This module — route-level FastAPI ``Depends`` only

Never import ``backend.dependencies`` from this module (circular risk with app_factory).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import jwt

from api.auth_tokens import decode_token
from backend.db.session import open_db_session

security = HTTPBearer(auto_error=False)

__all__ = [
    "CurrentTenant",
    "CurrentUser",
    "DBSession",
    "RequireAdmin",
    "RequireManager",
    "RequireSuperAdmin",
    "TenantContext",
    "UserContext",
    "get_current_tenant",
    "get_current_user",
    "get_db_session",
    "user_context_from_token",
]


# -- Database Session -----------------------------------------------------

async def get_db_session() -> AsyncGenerator:
    """Yield an async database session (maps RuntimeError → HTTP 500)."""
    try:
        async with open_db_session() as session:
            yield session
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not initialized",
        )


DBSession = Depends(get_db_session)


# -- Current User ---------------------------------------------------------

def user_context_from_token(token: str) -> "UserContext":
    """Build a UserContext from a verified access token (pure helper; unit-testable)."""
    try:
        claims = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if claims.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    def _as_uuid(value: object) -> uuid.UUID:
        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError):
            return uuid.uuid5(uuid.NAMESPACE_DNS, str(value) or "anonymous")

    return UserContext(
        id=_as_uuid(claims.get("sub")),
        email=claims.get("email", ""),
        role=claims.get("role", "viewer"),
        tenant_id=_as_uuid(claims.get("tid")),
    )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> "UserContext":
    """Resolve the current user by verifying the Bearer JWT (real signature check)."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_context_from_token(credentials.credentials)


class UserContext:
    """Lightweight user context for dependency injection."""

    def __init__(
        self,
        id: uuid.UUID,
        email: str,
        role: str,
        tenant_id: uuid.UUID,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_active: bool = True,
    ):
        self.id = id
        self.email = email
        self.role = role
        self.tenant_id = tenant_id
        self.first_name = first_name
        self.last_name = last_name
        self.is_active = is_active

    def has_role(self, min_role: str) -> bool:
        """Check if user has at least the given role level."""
        role_hierarchy = {"viewer": 0, "agent": 1, "manager": 2, "admin": 3, "super_admin": 4}
        user_level = role_hierarchy.get(self.role, -1)
        required_level = role_hierarchy.get(min_role, 999)
        return user_level >= required_level

    def to_profile(self) -> "UserProfile":
        """Convert to UserProfile schema."""
        from api.schemas.auth import UserProfile

        return UserProfile(
            id=self.id,
            email=self.email,
            first_name=self.first_name,
            last_name=self.last_name,
            role=self.role,
            is_active=self.is_active,
            email_verified=True,
            last_login_at=None,
            created_at=datetime.utcnow(),
        )


CurrentUser = Depends(get_current_user)


# -- Current Tenant -------------------------------------------------------

_PUBLIC_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _public_tenant_context() -> "TenantContext":
    """Stable public fallback tenant (unauthenticated / unresolved routes)."""
    return TenantContext(
        id=_PUBLIC_TENANT_ID,
        name="public",
        slug="public",
        plan="free",
        status="active",
    )


async def get_current_tenant(request: Request) -> "TenantContext":
    """Resolve current tenant from request state (set by TenantMiddleware)."""
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        return _public_tenant_context()

    if hasattr(tenant, "tenant_id"):
        return TenantContext(
            id=tenant.tenant_id,
            name=tenant.name,
            slug=tenant.slug,
            plan=tenant.plan,
            timezone=tenant.timezone,
            status=tenant.status,
            max_calls_monthly=tenant.max_calls_monthly,
        )

    if isinstance(tenant, TenantContext):
        return tenant

    return _public_tenant_context()


class TenantContext:
    """Lightweight tenant context for dependency injection."""

    def __init__(
        self,
        id: uuid.UUID,
        name: str,
        slug: str,
        plan: str = "free",
        timezone: str = "America/New_York",
        status: str = "active",
        max_calls_monthly: int = 100,
    ):
        self.id = id
        self.name = name
        self.slug = slug
        self.plan = plan
        self.timezone = timezone
        self.status = status
        self.max_calls_monthly = max_calls_monthly

    def is_active(self) -> bool:
        return self.status in ("active", "limited")


CurrentTenant = Depends(get_current_tenant)


# -- Role-based Access ----------------------------------------------------

class RoleRequirement:
    """Dependency factory for role-based access control."""

    def __init__(self, min_role: str):
        self.min_role = min_role

    async def __call__(self, user: UserContext = CurrentUser) -> UserContext:
        if not user.has_role(self.min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {self.min_role} role or higher",
            )
        return user


_require_admin = RoleRequirement("admin")
_require_super_admin = RoleRequirement("super_admin")
_require_manager = RoleRequirement("manager")

RequireAdmin = Depends(_require_admin)
RequireSuperAdmin = Depends(_require_super_admin)
RequireManager = Depends(_require_manager)