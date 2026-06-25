"""api/dependencies.py - FastAPI dependencies for auth, DB, tenant."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import jwt

from api.auth_tokens import decode_token

security = HTTPBearer(auto_error=False)


# -- Database Session -----------------------------------------------------

async def get_db_session() -> AsyncGenerator:
    """Yield an async database session via the backend engine."""
    from backend.dependencies import get_session_maker
    session_maker = get_session_maker()
    if session_maker is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not initialized",
        )
    session = session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


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

async def get_current_tenant(request: Request) -> "TenantContext":
    """Resolve current tenant from request state (set by TenantMiddleware)."""
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        # Return a minimal tenant context for route wiring
        return TenantContext(
            id=uuid.uuid4(),
            name="Default Tenant",
            slug="default",
            plan="free",
        )
    return tenant


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


RequireAdmin = RoleRequirement("admin")
RequireSuperAdmin = RoleRequirement("super_admin")
RequireManager = RoleRequirement("manager")
