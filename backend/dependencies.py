"""
Owlbell — FastAPI Dependencies.

Location: backend/dependencies.py

Provides all FastAPI dependency injectors used across the API layer:
- Database sessions (async SQLAlchemy)
- Redis connection
- Tenant resolution
- JWT authentication and authorization
- AI pipeline services
- Call management / telephony
- Event bus
- Circuit breaker
- Usage tracking / billing

Usage in route handlers:
    from backend.dependencies import (
        get_db_session, get_current_user, get_current_tenant, get_ai_pipeline
    )

    @router.get("/calls")
    async def list_calls(
        db: AsyncSession = Depends(get_db_session),
        tenant: TenantContext = Depends(get_current_tenant),
        user: UserContext = Depends(get_current_user),
    ):
        ...
"""

from __future__ import annotations

import logging
import uuid
from typing import AsyncGenerator, Dict, Optional

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import get_settings
from backend.db.cache.client import get_redis_client

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Globals (initialized at app startup via lifespan)
# ---------------------------------------------------------------------------

_engine = None
_session_maker = None

# ---------------------------------------------------------------------------
# Database Session
# ---------------------------------------------------------------------------


def init_engine() -> None:
    """Initialize the async SQLAlchemy engine (called once at startup)."""
    global _engine, _session_maker
    if _engine is not None:
        return
    settings = get_settings()
    _engine = create_async_engine(
        settings.database_url,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=settings.database.pool_recycle,
        pool_pre_ping=settings.database.pool_pre_ping,
        echo=settings.is_development,
    )
    _session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    logger.info("dependencies.engine_initialized")


def get_engine():
    """Return the global engine instance."""
    return _engine


def get_session_maker():
    """Return the global session maker."""
    return _session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session with automatic cleanup.

    Usage:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    if _session_maker is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    session = _session_maker()
    try:
        yield session
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        logger.error("dependencies.db_error", error=str(exc))
        raise
    finally:
        await session.close()


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------


async def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client.

    The client is a singleton managed by backend.db.cache.client.
    """
    return await get_redis_client()


# ---------------------------------------------------------------------------
# User Context
# ---------------------------------------------------------------------------


class UserContext:
    """Authenticated user context attached to request.state."""

    def __init__(
        self,
        id: uuid.UUID,
        email: str,
        role: str,
        tenant_id: uuid.UUID,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        is_active: bool = True,
        email_verified: bool = True,
        permissions: Optional[list[str]] = None,
    ):
        self.id = id
        self.email = email
        self.role = role
        self.tenant_id = tenant_id
        self.first_name = first_name
        self.last_name = last_name
        self.is_active = is_active
        self.email_verified = email_verified
        self.permissions = permissions or []

    def has_role(self, min_role: str) -> bool:
        """Check if user has at least the given role level."""
        role_hierarchy = {
            "viewer": 0,
            "agent": 1,
            "manager": 2,
            "admin": 3,
            "super_admin": 4,
        }
        user_level = role_hierarchy.get(self.role, -1)
        required_level = role_hierarchy.get(min_role, 999)
        return user_level >= required_level

    def to_dict(self) -> Dict:
        return {
            "id": str(self.id),
            "email": self.email,
            "role": self.role,
            "tenant_id": str(self.tenant_id),
            "first_name": self.first_name,
            "last_name": self.last_name,
            "is_active": self.is_active,
        }


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserContext:
    """Resolve the current user from JWT in the Authorization header.

    Raises:
        HTTPException(401): If no credentials or invalid token.
        HTTPException(403): If user is inactive.
    """
    settings = get_settings()

    # Allow pre-authenticated user from middleware or testing
    user = getattr(request.state, "user", None)
    if user is not None and isinstance(user, UserContext):
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )
        return user

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.security.jwt_secret.get_secret_value(),
            algorithms=[settings.security.jwt_algorithm],
        )
        user_id_str: Optional[str] = payload.get("sub")
        tenant_id_str: Optional[str] = payload.get("tid")
        email: Optional[str] = payload.get("email")
        role: Optional[str] = payload.get("role", "viewer")

        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
            )

        user_id = uuid.UUID(user_id_str)
        tenant_id = uuid.UUID(tenant_id_str) if tenant_id_str else uuid.uuid4()

        user_ctx = UserContext(
            id=user_id,
            email=email or "unknown@owlbell.xyz",
            role=role,
            tenant_id=tenant_id,
            first_name=payload.get("first_name"),
            last_name=payload.get("last_name"),
            is_active=payload.get("is_active", True),
            email_verified=payload.get("email_verified", False),
        )

        if not user_ctx.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        # Attach to request state for downstream use
        request.state.user = user_ctx
        return user_ctx

    except JWTError as exc:
        logger.warning("dependencies.jwt_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Tenant Context
# ---------------------------------------------------------------------------


class TenantContext:
    """Tenant context resolved from request."""

    def __init__(
        self,
        id: uuid.UUID,
        name: str,
        slug: str,
        plan: str = "free",
        timezone: str = "America/New_York",
        status: str = "active",
        max_calls_monthly: int = 100,
        calls_used_this_period: int = 0,
        features: Optional[Dict] = None,
    ):
        self.id = id
        self.name = name
        self.slug = slug
        self.plan = plan
        self.timezone = timezone
        self.status = status
        self.max_calls_monthly = max_calls_monthly
        self.calls_used_this_period = calls_used_this_period
        self.features = features or {}

    def is_active(self) -> bool:
        return self.status in ("active", "limited")

    def is_within_call_limit(self) -> bool:
        if self.max_calls_monthly == 0:  # unlimited
            return True
        return self.calls_used_this_period < self.max_calls_monthly

    def to_dict(self) -> Dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "plan": self.plan,
            "timezone": self.timezone,
            "status": self.status,
        }


async def get_current_tenant(request: Request) -> TenantContext:
    """Resolve current tenant from request state or database."""
    # Try to get from request state (set by middleware)
    tenant = getattr(request.state, "tenant", None)
    if tenant is not None and isinstance(tenant, TenantContext):
        return tenant

    # Try from user context
    user = getattr(request.state, "user", None)
    if isinstance(user, UserContext):
        # Load actual tenant from database
        if _session_maker is not None:
            session = _session_maker()
            try:
                from sqlalchemy import select
                from backend.db.models.tenant import Tenant

                result = await session.execute(
                    select(Tenant).where(Tenant.id == user.tenant_id)
                )
                db_tenant = result.scalar_one_or_none()
                if db_tenant:
                    return TenantContext(
                        id=db_tenant.id,
                        name=db_tenant.name,
                        slug=db_tenant.slug,
                        plan=db_tenant.plan_tier.value if hasattr(db_tenant.plan_tier, 'value') else str(db_tenant.plan_tier),
                        timezone=db_tenant.business_timezone,
                        status=db_tenant.status.value if hasattr(db_tenant.status, 'value') else str(db_tenant.status),
                    )
            except Exception:
                pass
            finally:
                await session.close()

        # Fallback if DB query fails
        return TenantContext(
            id=user.tenant_id,
            name="Default Tenant",
            slug="default",
            plan="free",
        )

    # Fallback for unauthenticated routes
    return TenantContext(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Public",
        slug="public",
        plan="free",
    )


# ---------------------------------------------------------------------------
# Role-based Access
# ---------------------------------------------------------------------------


class RoleRequirement:
    """Dependency factory for role-based access control.

    Usage:
        @router.post("/admin-only")
        async def admin_action(user: UserContext = Depends(RequireAdmin)):
            ...
    """

    def __init__(self, min_role: str):
        self.min_role = min_role

    async def __call__(self, user: UserContext = Depends(get_current_user)) -> UserContext:
        if not user.has_role(self.min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {self.min_role} role or higher",
            )
        return user


RequireAdmin = RoleRequirement("admin")
RequireSuperAdmin = RoleRequirement("super_admin")
RequireManager = RoleRequirement("manager")


# ---------------------------------------------------------------------------
# AI Pipeline
# ---------------------------------------------------------------------------


class AIPipelineContext:
    """Context object providing access to AI pipeline services.

    This is a lazy-loading wrapper that initializes services on first use.
    """

    def __init__(self):
        self._whisper = None
        self._ollama = None
        self._piper = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all AI service clients."""
        if self._initialized:
            return
        try:
            from backend.ai.stt.whisper_service import get_whisper_service
            from backend.ai.llm.ollama_client import get_ollama_client
            from backend.ai.tts.piper_service import get_piper_service

            self._whisper = get_whisper_service()
            self._ollama = get_ollama_client()
            self._piper = get_piper_service()
            self._initialized = True
            logger.info("dependencies.ai_pipeline_initialized")
        except Exception as exc:
            logger.error("dependencies.ai_init_failed", error=str(exc))
            raise

    @property
    def whisper(self):
        return self._whisper

    @property
    def ollama(self):
        return self._ollama

    @property
    def piper(self):
        return self._piper

    async def health_check(self) -> Dict[str, bool]:
        """Check health of all AI services."""
        results = {
            "whisper": False,
            "ollama": False,
            "piper": False,
        }
        if self._whisper is not None:
            try:
                results["whisper"] = await self._whisper.is_healthy()
            except Exception:
                pass
        if self._ollama is not None:
            try:
                results["ollama"] = await self._ollama.is_healthy()
            except Exception:
                pass
        if self._piper is not None:
            try:
                results["piper"] = await self._piper.is_healthy()
            except Exception:
                pass
        return results


# Global pipeline context (initialized once)
_ai_pipeline: Optional[AIPipelineContext] = None


async def get_ai_pipeline() -> AIPipelineContext:
    """Return the shared AI pipeline context (initializing if needed)."""
    global _ai_pipeline
    if _ai_pipeline is None:
        _ai_pipeline = AIPipelineContext()
    if not _ai_pipeline._initialized:
        await _ai_pipeline.initialize()
    return _ai_pipeline


# ---------------------------------------------------------------------------
# Call Manager (Telephony)
# ---------------------------------------------------------------------------


class CallManagerContext:
    """Context providing access to telephony services."""

    def __init__(self):
        self._esl_client = None
        self._session_manager = None
        self._event_bus = None

    async def initialize(self) -> None:
        """Initialize telephony connections."""
        try:
            # Session manager and event bus are wired via dependencies
            from orchestrator.session_manager import SessionManager
            from orchestrator.event_bus import EventBus

            redis_client = await get_redis_client()
            self._session_manager = SessionManager(redis_client)
            self._event_bus = EventBus(redis_client)
            logger.info("dependencies.call_manager_initialized")
        except Exception as exc:
            logger.error("dependencies.call_manager_init_failed", error=str(exc))

    @property
    def session_manager(self):
        return self._session_manager

    @property
    def event_bus(self):
        return self._event_bus


_call_manager: Optional[CallManagerContext] = None


async def get_call_manager() -> CallManagerContext:
    """Return the shared call manager context."""
    global _call_manager
    if _call_manager is None:
        _call_manager = CallManagerContext()
        await _call_manager.initialize()
    return _call_manager


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------


async def get_event_bus() -> "EventBus":
    """Return the shared EventBus instance."""
    from orchestrator.event_bus import EventBus

    redis_client = await get_redis_client()
    return EventBus(redis_client)


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


async def get_circuit_breaker(name: str = "default") -> "CircuitBreaker":
    """Return a circuit breaker for the given service name."""
    from orchestrator.circuit_breaker import get_circuit_breaker as _get_cb

    redis_client = await get_redis_client()
    return _get_cb(name, redis_client=redis_client)


# ---------------------------------------------------------------------------
# Billing / Usage Tracker
# ---------------------------------------------------------------------------


_usage_tracker: Optional["UsageTracker"] = None


async def get_usage_tracker() -> "UsageTracker":
    """Return the shared, DB-backed usage tracker for billing.

    The tracker persists every billable event to the ``usage_records`` table
    via the global async session maker. A single instance is shared so its
    in-memory counters stay consistent within the process.
    """
    global _usage_tracker
    if _usage_tracker is None:
        from operations.billing.tracker import UsageTracker

        _usage_tracker = UsageTracker(session_maker=_session_maker)
    return _usage_tracker


# ---------------------------------------------------------------------------
# Prompt Manager
# ---------------------------------------------------------------------------


_prompt_manager: Optional["PromptManager"] = None


async def get_prompt_manager() -> "PromptManager":
    """Return the shared, DB-backed prompt manager.

    Persists prompt versions and A/B tests to Postgres via the global session
    maker. Shared as a singleton across the process.
    """
    global _prompt_manager
    if _prompt_manager is None:
        from operations.prompts.manager import PromptManager

        _prompt_manager = PromptManager(session_maker=_session_maker)
    return _prompt_manager


# ---------------------------------------------------------------------------
# Combined dependency for common route signatures
# ---------------------------------------------------------------------------


async def get_db_and_tenant(
    db: AsyncSession = Depends(get_db_session),
    tenant: TenantContext = Depends(get_current_tenant),
) -> Dict:
    """Convenience dependency that provides both db session and tenant."""
    return {"db": db, "tenant": tenant}


async def get_full_context(
    db: AsyncSession = Depends(get_db_session),
    tenant: TenantContext = Depends(get_current_tenant),
    user: UserContext = Depends(get_current_user),
    redis_client: aioredis.Redis = Depends(get_redis),
) -> Dict:
    """Full context dependency with db, tenant, user, and redis."""
    return {
        "db": db,
        "tenant": tenant,
        "user": user,
        "redis": redis_client,
    }


# ---------------------------------------------------------------------------
# Startup / Shutdown helpers
# ---------------------------------------------------------------------------


async def close_all_dependencies() -> None:
    """Close all shared resources (called during shutdown)."""
    global _engine, _session_maker, _ai_pipeline, _call_manager
    global _usage_tracker, _prompt_manager

    logger.info("dependencies.shutdown_start")

    # Reset shared operation services
    _usage_tracker = None
    _prompt_manager = None

    # Close AI pipeline
    if _ai_pipeline is not None:
        _ai_pipeline = None
        logger.info("dependencies.ai_pipeline_closed")

    # Close call manager
    if _call_manager is not None:
        _call_manager = None
        logger.info("dependencies.call_manager_closed")

    # Close database engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None
        logger.info("dependencies.engine_disposed")

    logger.info("dependencies.shutdown_complete")
