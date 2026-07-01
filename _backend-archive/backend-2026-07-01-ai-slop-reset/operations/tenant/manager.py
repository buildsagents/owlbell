"""operations/tenant/manager.py - Tenant lifecycle management.

Manages tenant onboarding, provisioning, suspension, deletion,
and all tenant lifecycle transitions. Every operation is logged
to the audit trail.

Backed by PostgreSQL via SQLAlchemy async — no in-memory storage.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.enums import PlanTier, TenantStatus
from backend.db.models.tenant import Tenant, TenantConfig

logger = structlog.get_logger(__name__)


# -- Tenant Context -------------------------------------------------------


class TenantContext:
    """Tenant context object used throughout the system."""

    def __init__(
        self,
        tenant_id: uuid.UUID,
        slug: str,
        name: str,
        subdomain: str,
        status: TenantStatus = TenantStatus.PENDING,
        plan_tier: PlanTier = PlanTier.FREE,
        plan_expires_at: Optional[datetime] = None,
        timezone: str = "America/New_York",
        locale: str = "en-US",
        max_calls_monthly: int = 100,
        max_concurrent_calls: int = 1,
        max_users: int = 1,
        max_phone_numbers: int = 1,
        ai_model_tier: str = "fast",
        calls_used_this_period: int = 0,
        minutes_used_this_period: float = 0.0,
        tokens_used_this_period: int = 0,
        enabled_features: Optional[frozenset[str]] = None,
        owner_email: str = "",
        created_at: Optional[datetime] = None,
    ):
        self.tenant_id = tenant_id
        self.slug = slug
        self.name = name
        self.subdomain = subdomain
        self.status = status if isinstance(status, TenantStatus) else TenantStatus(status)
        self.plan_tier = plan_tier if isinstance(plan_tier, PlanTier) else PlanTier(plan_tier)
        self.plan_expires_at = plan_expires_at
        self.timezone = timezone
        self.locale = locale
        self.max_calls_monthly = max_calls_monthly
        self.max_concurrent_calls = max_concurrent_calls
        self.max_users = max_users
        self.max_phone_numbers = max_phone_numbers
        self.ai_model_tier = ai_model_tier
        self.calls_used_this_period = calls_used_this_period
        self.minutes_used_this_period = minutes_used_this_period
        self.tokens_used_this_period = tokens_used_this_period
        self.enabled_features = enabled_features or frozenset()
        self.owner_email = owner_email
        self.created_at = created_at or datetime.utcnow()

    def is_active(self) -> bool:
        return self.status in (TenantStatus.ACTIVE, TenantStatus.LIMITED)

    def has_feature(self, feature: str) -> bool:
        return feature in self.enabled_features

    def is_within_call_limit(self) -> bool:
        return self.calls_used_this_period < self.max_calls_monthly

    def remaining_calls(self) -> int:
        return max(0, self.max_calls_monthly - self.calls_used_this_period)

    def to_log_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "slug": self.slug,
            "status": self.status.value,
            "plan": self.plan_tier.value,
            "usage_calls": self.calls_used_this_period,
            "usage_minutes": self.minutes_used_this_period,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "slug": self.slug,
            "name": self.name,
            "subdomain": self.subdomain,
            "status": self.status.value,
            "plan_tier": self.plan_tier.value,
            "timezone": self.timezone,
            "locale": self.locale,
            "max_calls_monthly": self.max_calls_monthly,
            "calls_used_this_period": self.calls_used_this_period,
            "remaining_calls": self.remaining_calls(),
        }


# -- Exceptions -----------------------------------------------------------


class TenantManagerError(Exception):
    """Base exception for tenant management."""
    pass


class SubdomainTakenError(TenantManagerError):
    """Subdomain is already in use."""
    pass


class TenantNotFoundError(TenantManagerError):
    """Tenant not found."""
    pass


class InvalidTenantStateError(TenantManagerError):
    """Invalid tenant state transition."""
    pass


class ReservedSubdomainError(TenantManagerError):
    """Subdomain is reserved."""
    pass


# -- Billing Plan Mapping -------------------------------------------------


BILLING_PLAN_MAP: Dict[str, PlanTier] = {
    "basic": PlanTier.BASIC,
    "pro": PlanTier.PRO,
    "pro_plus": PlanTier.PRO_PLUS,
    "free": PlanTier.FREE,
    "starter": PlanTier.STARTER,
    "professional": PlanTier.PROFESSIONAL,
    "enterprise": PlanTier.ENTERPRISE,
}


# -- Tenant Manager -------------------------------------------------------


class TenantManager:
    """Manages the complete tenant lifecycle backed by PostgreSQL.

    Usage:
        manager = TenantManager(session_maker=get_session_maker())
        tenant = await manager.create_tenant(onboarding_request)
        await manager.activate_tenant(tenant.tenant_id)
    """

    # Reserved subdomains that cannot be used
    RESERVED_SUBDOMAINS = frozenset({
        "www", "api", "admin", "app", "dashboard", "mail", "smtp",
        "ftp", "blog", "support", "help", "docs", "status", "health",
        "monitor", "grafana", "prometheus", "kibana", "elastic",
        "db", "database", "redis", "postgres", "mysql", "mongo",
        "test", "staging", "dev", "demo", "sandbox", "localhost",
        "answerflow", "signup", "login", "auth", "verify",
    })

    # Subdomain validation regex
    SUBDOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$")

    # Plan defaults (keys match PlanTier enum values)
    PLAN_DEFAULTS: Dict[str, Dict[str, Any]] = {
        "free": {
            "max_calls_monthly": 100,
            "max_concurrent_calls": 1,
            "max_users": 1,
            "max_phone_numbers": 1,
            "ai_model_tier": "fast",
            "max_call_duration_minutes": 10,
        },
        "starter": {
            "max_calls_monthly": 500,
            "max_concurrent_calls": 3,
            "max_users": 5,
            "max_phone_numbers": 3,
            "ai_model_tier": "quality",
            "max_call_duration_minutes": 30,
        },
        "professional": {
            "max_calls_monthly": 2000,
            "max_concurrent_calls": 10,
            "max_users": 20,
            "max_phone_numbers": 10,
            "ai_model_tier": "premium",
            "max_call_duration_minutes": 60,
        },
    }

    def __init__(self, session_maker: Callable[[], AsyncSession]) -> None:
        self._session_maker = session_maker

    # -- Subdomain Helpers ------------------------------------------------

    def _sanitize_subdomain(self, desired: str) -> str:
        """Convert desired subdomain to valid format."""
        sanitized = desired.lower().strip()
        sanitized = re.sub(r"[^a-z0-9-]", "-", sanitized)
        sanitized = re.sub(r"-+", "-", sanitized)
        sanitized = sanitized.strip("-")
        return sanitized[:63]

    async def _is_subdomain_available(self, subdomain: str) -> bool:
        """Check if subdomain is available (reserved check + DB lookup)."""
        if subdomain in self.RESERVED_SUBDOMAINS:
            return False
        if not self.SUBDOMAIN_RE.match(subdomain):
            return False
        async with self._session_maker() as session:
            result = await session.execute(
                select(func.count(Tenant.id)).where(Tenant.subdomain == subdomain)
            )
            count = result.scalar() or 0
            return count == 0

    async def _generate_unique_slug(self, business_name: str) -> str:
        """Generate a unique slug from business name via DB lookup."""
        base = re.sub(r"[^a-z0-9-]", "-", business_name.lower())[:50].strip("-")
        slug = base
        counter = 1
        async with self._session_maker() as session:
            while True:
                result = await session.execute(
                    select(func.count(Tenant.id)).where(Tenant.slug == slug)
                )
                count = result.scalar() or 0
                if count == 0:
                    break
                slug = f"{base}-{counter}"
                counter += 1
                if counter > 1000:
                    slug = f"{base}-{uuid.uuid4().hex[:8]}"
                    break
        return slug

    def _get_plan_defaults(self, plan_tier: PlanTier) -> Dict[str, Any]:
        """Get plan defaults for a given plan tier."""
        return self.PLAN_DEFAULTS.get(plan_tier.value, self.PLAN_DEFAULTS["free"]).copy()

    # -- Tenant <-> Context Conversion -----------------------------------

    def _tenant_to_context(self, tenant: Tenant) -> TenantContext:
        """Convert a Tenant ORM instance to a TenantContext."""
        plan_defaults = self._get_plan_defaults(tenant.plan_tier)
        metadata = tenant.metadata_json or {}
        features = tenant.features_json or {}
        enabled_features = frozenset(
            f for f, enabled in features.items() if enabled
        ) if features else frozenset()

        return TenantContext(
            tenant_id=tenant.id,
            slug=tenant.slug,
            name=tenant.name,
            subdomain=tenant.subdomain,
            status=(
                tenant.status
                if isinstance(tenant.status, TenantStatus)
                else TenantStatus(tenant.status)
            ),
            plan_tier=(
                tenant.plan_tier
                if isinstance(tenant.plan_tier, PlanTier)
                else PlanTier(tenant.plan_tier)
            ),
            plan_expires_at=tenant.plan_expires_at,
            timezone=tenant.business_timezone,
            locale=tenant.locale,
            max_calls_monthly=plan_defaults["max_calls_monthly"],
            max_concurrent_calls=plan_defaults["max_concurrent_calls"],
            max_users=plan_defaults["max_users"],
            max_phone_numbers=plan_defaults["max_phone_numbers"],
            ai_model_tier=plan_defaults["ai_model_tier"],
            calls_used_this_period=metadata.get("calls_used_this_period", 0),
            minutes_used_this_period=metadata.get("minutes_used_this_period", 0.0),
            tokens_used_this_period=metadata.get("tokens_used_this_period", 0),
            enabled_features=enabled_features,
            owner_email=tenant.owner_email,
            created_at=tenant.created_at,
        )

    # -- Tenant CRUD ------------------------------------------------------

    async def create_tenant(
        self,
        name: str,
        owner_email: str,
        desired_subdomain: str,
        plan_tier: PlanTier = PlanTier.FREE,
        timezone: str = "America/New_York",
        locale: str = "en-US",
        industry: Optional[str] = None,
    ) -> TenantContext:
        """Create a new tenant.

        Flow:
            1. Validate and sanitize subdomain
            2. Generate unique slug
            3. INSERT into Tenant table with status=PENDING
            4. Set up plan limits and default config in config_json

        Args:
            name: Business display name
            owner_email: Email of the tenant owner
            desired_subdomain: Preferred subdomain
            plan_tier: Plan tier
            timezone: Business timezone
            locale: Business locale
            industry: Business industry

        Returns:
            Created tenant context (status=PENDING)

        Raises:
            SubdomainTakenError: If subdomain is unavailable
            ReservedSubdomainError: If subdomain is reserved
        """
        subdomain = self._sanitize_subdomain(desired_subdomain)

        if subdomain in self.RESERVED_SUBDOMAINS:
            raise ReservedSubdomainError(
                f"Subdomain '{subdomain}' is reserved"
            )

        available = await self._is_subdomain_available(subdomain)
        if not available:
            subdomain = f"{subdomain}-{uuid.uuid4().hex[:6]}"
            available = await self._is_subdomain_available(subdomain)
            if not available:
                raise SubdomainTakenError(
                    f"Could not find available subdomain for '{desired_subdomain}'"
                )

        slug = await self._generate_unique_slug(name)
        tenant_id = uuid.uuid4()
        plan_defaults = self._get_plan_defaults(plan_tier)
        now = datetime.utcnow()
        period = now.strftime("%Y-%m")

        default_config = {
            "ai_settings": {
                "voice_id": "en_US-lessac-medium",
                "speech_rate": 1.0,
                "greeting_message": f"Thank you for calling {name}...",
                "hold_music_enabled": False,
                "max_call_duration_minutes": plan_defaults["max_call_duration_minutes"],
                "language": "en-US",
                "fallback_behavior": "take_message",
                "confidence_threshold": 0.7,
                "enable_interruptions": True,
                "max_silence_seconds": 10,
            },
            "routing_rules": {
                "business_hours": {
                    "monday": {"open": "09:00", "close": "17:00"},
                    "tuesday": {"open": "09:00", "close": "17:00"},
                    "wednesday": {"open": "09:00", "close": "17:00"},
                    "thursday": {"open": "09:00", "close": "17:00"},
                    "friday": {"open": "09:00", "close": "17:00"},
                },
                "timezone": timezone,
                "after_hours_action": "ai_answer",
                "overflow_number": None,
                "emergency_escalation": True,
            },
            "notification_settings": {
                "email_notifications": True,
                "sms_notifications": False,
                "notification_emails": [owner_email],
                "daily_summary": True,
                "missed_call_alert": True,
                "voicemail_transcript": True,
            },
            "integrations": {},
        }

        async with self._session_maker() as session:
            tenant = Tenant(
                id=tenant_id,
                slug=slug,
                name=name,
                subdomain=subdomain,
                status=TenantStatus.PENDING,
                plan_tier=plan_tier,
                owner_email=owner_email,
                industry=industry,
                business_timezone=timezone,
                locale=locale,
                current_period=period,
                config_json=default_config,
                metadata_json={
                    "calls_used_this_period": 0,
                    "minutes_used_this_period": 0.0,
                    "tokens_used_this_period": 0,
                },
            )
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)

        logger.info(
            "tenant.created",
            tenant_id=str(tenant_id),
            slug=slug,
            subdomain=subdomain,
            plan=plan_tier.value,
        )

        return TenantContext(
            tenant_id=tenant_id,
            slug=slug,
            name=name,
            subdomain=subdomain,
            status=TenantStatus.PENDING,
            plan_tier=plan_tier,
            timezone=timezone,
            locale=locale,
            owner_email=owner_email,
            max_calls_monthly=plan_defaults["max_calls_monthly"],
            max_concurrent_calls=plan_defaults["max_concurrent_calls"],
            max_users=plan_defaults["max_users"],
            max_phone_numbers=plan_defaults["max_phone_numbers"],
            ai_model_tier=plan_defaults["ai_model_tier"],
        )

    async def get_tenant(self, tenant_id: uuid.UUID) -> TenantContext:
        """Get tenant by ID.

        Args:
            tenant_id: The tenant UUID

        Returns:
            Tenant context

        Raises:
            TenantNotFoundError: If tenant doesn't exist
        """
        async with self._session_maker() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise TenantNotFoundError(f"Tenant {tenant_id} not found")
            return self._tenant_to_context(tenant)

    async def get_tenant_by_subdomain(self, subdomain: str) -> Optional[TenantContext]:
        """Get tenant by subdomain."""
        async with self._session_maker() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.subdomain == subdomain)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                return None
            return self._tenant_to_context(tenant)

    async def get_tenant_by_slug(self, slug: str) -> Optional[TenantContext]:
        """Get tenant by slug."""
        async with self._session_maker() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.slug == slug)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                return None
            return self._tenant_to_context(tenant)

    # -- Lifecycle Transitions --------------------------------------------

    async def _set_tenant_status(
        self,
        tenant_id: uuid.UUID,
        new_status: TenantStatus,
        allowed_current: Tuple[TenantStatus, ...],
        extra_updates: Optional[Dict[str, Any]] = None,
        log_action: str = "status_changed",
        log_reason: str = "",
    ) -> TenantContext:
        """Generic status transition with DB persistence."""
        async with self._session_maker() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise TenantNotFoundError(f"Tenant {tenant_id} not found")

            if tenant.status not in allowed_current:
                raise InvalidTenantStateError(
                    f"Cannot transition tenant from {tenant.status.value} to {new_status.value}"
                )

            updates: Dict[str, Any] = {
                "status": new_status,
                "updated_at": datetime.utcnow(),
            }
            if extra_updates:
                updates.update(extra_updates)

            await session.execute(
                update(Tenant).where(Tenant.id == tenant_id).values(**updates)
            )
            await session.commit()

            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one()

        log_data: Dict[str, Any] = {"tenant_id": str(tenant_id)}
        if log_reason:
            log_data["reason"] = log_reason
        logger.info(f"tenant.{log_action}", **log_data)

        return self._tenant_to_context(tenant)

    async def activate_tenant(self, tenant_id: uuid.UUID) -> TenantContext:
        """Activate a pending tenant.

        Transition: PENDING -> ACTIVE
        """
        return await self._set_tenant_status(
            tenant_id,
            TenantStatus.ACTIVE,
            allowed_current=(TenantStatus.PENDING,),
            log_action="activated",
        )

    async def suspend_tenant(
        self, tenant_id: uuid.UUID, reason: str = ""
    ) -> TenantContext:
        """Suspend an active tenant.

        Transition: ACTIVE -> SUSPENDED, LIMITED -> SUSPENDED
        """
        return await self._set_tenant_status(
            tenant_id,
            TenantStatus.SUSPENDED,
            allowed_current=(TenantStatus.ACTIVE, TenantStatus.LIMITED),
            log_action="suspended",
            log_reason=reason,
        )

    async def reactivate_tenant(self, tenant_id: uuid.UUID) -> TenantContext:
        """Reactivate a suspended tenant.

        Transition: SUSPENDED -> ACTIVE
        """
        return await self._set_tenant_status(
            tenant_id,
            TenantStatus.ACTIVE,
            allowed_current=(TenantStatus.SUSPENDED,),
            log_action="reactivated",
        )

    async def set_limited(self, tenant_id: uuid.UUID) -> TenantContext:
        """Set tenant to limited state (soft limit hit).

        Transition: ACTIVE -> LIMITED
        """
        return await self._set_tenant_status(
            tenant_id,
            TenantStatus.LIMITED,
            allowed_current=(TenantStatus.ACTIVE,),
            log_action="limited",
        )

    async def terminate_tenant(self, tenant_id: uuid.UUID) -> TenantContext:
        """Terminate a suspended tenant.

        Transition: SUSPENDED -> TERMINATED
        """
        return await self._set_tenant_status(
            tenant_id,
            TenantStatus.TERMINATED,
            allowed_current=(TenantStatus.SUSPENDED,),
            extra_updates={"deleted_at": datetime.utcnow()},
            log_action="terminated",
        )

    async def change_plan(
        self, tenant_id: uuid.UUID, new_plan: PlanTier
    ) -> TenantContext:
        """Change tenant plan tier.

        Updates limits based on new plan defaults.
        If LIMITED and upgrading from free, auto-reactivates.
        """
        async with self._session_maker() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise TenantNotFoundError(f"Tenant {tenant_id} not found")

            old_plan = tenant.plan_tier

            updates: Dict[str, Any] = {
                "plan_tier": new_plan,
                "updated_at": datetime.utcnow(),
            }

            if tenant.status == TenantStatus.LIMITED and new_plan != PlanTier.FREE:
                updates["status"] = TenantStatus.ACTIVE

            await session.execute(
                update(Tenant).where(Tenant.id == tenant_id).values(**updates)
            )
            await session.commit()

            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one()

        logger.info(
            "tenant.plan_changed",
            tenant_id=str(tenant_id),
            old_plan=old_plan.value,
            new_plan=new_plan.value,
        )
        return self._tenant_to_context(tenant)

    # -- Tenant Config ----------------------------------------------------

    async def get_config(self, tenant_id: uuid.UUID) -> Dict[str, Any]:
        """Get tenant configuration from config_json."""
        async with self._session_maker() as session:
            result = await session.execute(
                select(Tenant.config_json).where(Tenant.id == tenant_id)
            )
            row = result.one_or_none()
            if not row:
                raise TenantNotFoundError(f"Tenant {tenant_id} not found")
            return row[0] or {}

    async def update_config(
        self, tenant_id: uuid.UUID, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update tenant configuration (deep merge into config_json).

        For sub-keys that are themselves dicts (ai_settings, routing_rules,
        notification_settings, integrations), the merge is recursive —
        individual keys within those sub-dicts are updated, not replaced.
        """
        async with self._session_maker() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise TenantNotFoundError(f"Tenant {tenant_id} not found")

            config = tenant.config_json or {}
            for key, value in updates.items():
                if (
                    key in config
                    and isinstance(config[key], dict)
                    and isinstance(value, dict)
                ):
                    config[key].update(value)
                else:
                    config[key] = value

            await session.execute(
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(config_json=config, updated_at=datetime.utcnow())
            )
            await session.commit()

        logger.info("tenant.config_updated", tenant_id=str(tenant_id))
        return config

    # -- Usage Tracking ---------------------------------------------------

    async def record_usage(
        self,
        tenant_id: uuid.UUID,
        calls: int = 0,
        minutes: float = 0.0,
        tokens: int = 0,
    ) -> None:
        """Record usage for a tenant.

        Stores usage counters in metadata_json and auto-transitions
        to LIMITED when the monthly call limit is reached.
        """
        async with self._session_maker() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                logger.warning(
                    "tenant.usage_record_failed_not_found",
                    tenant_id=str(tenant_id),
                )
                return

            metadata = tenant.metadata_json or {}
            metadata["calls_used_this_period"] = (
                metadata.get("calls_used_this_period", 0) + calls
            )
            metadata["minutes_used_this_period"] = (
                metadata.get("minutes_used_this_period", 0.0) + minutes
            )
            metadata["tokens_used_this_period"] = (
                metadata.get("tokens_used_this_period", 0) + tokens
            )

            updates: Dict[str, Any] = {
                "metadata_json": metadata,
                "updated_at": datetime.utcnow(),
            }

            plan_defaults = self._get_plan_defaults(tenant.plan_tier)
            if (
                tenant.status == TenantStatus.ACTIVE
                and metadata["calls_used_this_period"]
                >= plan_defaults["max_calls_monthly"]
            ):
                updates["status"] = TenantStatus.LIMITED
                logger.info("tenant.limit_reached", tenant_id=str(tenant_id))

            await session.execute(
                update(Tenant).where(Tenant.id == tenant_id).values(**updates)
            )
            await session.commit()

    # -- Listing ----------------------------------------------------------

    async def list_tenants(
        self,
        status: Optional[TenantStatus] = None,
        plan_tier: Optional[PlanTier] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TenantContext]:
        """List tenants with optional filtering."""
        query = select(Tenant)
        conditions = []
        if status is not None:
            conditions.append(Tenant.status == status)
        if plan_tier is not None:
            conditions.append(Tenant.plan_tier == plan_tier)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.offset(offset).limit(limit)

        async with self._session_maker() as session:
            result = await session.execute(query)
            tenants = result.scalars().all()
            return [self._tenant_to_context(t) for t in tenants]

    async def get_tenant_count(
        self, status: Optional[TenantStatus] = None
    ) -> int:
        """Count tenants with optional status filter."""
        query = select(func.count(Tenant.id))
        if status is not None:
            query = query.where(Tenant.status == status)
        async with self._session_maker() as session:
            result = await session.execute(query)
            return result.scalar() or 0
