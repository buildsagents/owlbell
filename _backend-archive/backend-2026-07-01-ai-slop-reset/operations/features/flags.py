"""operations/features/flags.py - Feature flags with gradual rollout.

Manages per-tenant feature flags with gradual rollout support,
plan-based gating, and override management.

Design: Feature flags are checked in-memory per request (<2ms target).
Gradual rollout uses tenant_id hash for deterministic assignment.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger(__name__)


class FeatureFlag:
    """Global feature flag definition.

    Attributes:
        name: Machine-readable name (e.g., "call_transcription")
        display_name: Human-readable name
        description: Flag description
        category: Category (ai, billing, ui, integration)
        default_enabled: Default for new tenants
        rollout_percentage: 0-100 for gradual rollout
        required_plan_tier: Minimum plan tier required
        is_active: Whether flag is active globally
    """

    def __init__(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        category: str = "general",
        default_enabled: bool = False,
        rollout_percentage: int = 100,
        required_plan_tier: Optional[str] = None,
        is_active: bool = True,
    ):
        self.id = uuid.uuid4()
        self.name = name
        self.display_name = display_name
        self.description = description
        self.category = category
        self.default_enabled = default_enabled
        self.rollout_percentage = rollout_percentage
        self.required_plan_tier = required_plan_tier
        self.is_active = is_active
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "default_enabled": self.default_enabled,
            "rollout_percentage": self.rollout_percentage,
            "required_plan_tier": self.required_plan_tier,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class FeatureFlagOverride:
    """Per-tenant feature flag override.

    NULL enabled = use flag default.
    """

    def __init__(
        self,
        tenant_id: uuid.UUID,
        flag_name: str,
        enabled: Optional[bool] = None,
        set_by: Optional[uuid.UUID] = None,
        set_reason: Optional[str] = None,
    ):
        self.id = uuid.uuid4()
        self.tenant_id = tenant_id
        self.flag_name = flag_name
        self.enabled = enabled
        self.set_by = set_by
        self.set_reason = set_reason
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "flag_name": self.flag_name,
            "enabled": self.enabled,
            "set_by": str(self.set_by) if self.set_by else None,
            "set_reason": self.set_reason,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class FeatureFlagService:
    """Feature flag service with rollout support.

    Usage:
        service = FeatureFlagService()
        is_enabled = await service.is_enabled("call_transcription", tenant_id, plan="starter")
        await service.set_override(tenant_id, "call_transcription", True, user_id)
    """

    # Built-in feature flags
    BUILT_IN_FLAGS: List[Dict[str, Any]] = [
        {
            "name": "call_transcription",
            "display_name": "Call Transcription",
            "category": "ai",
            "default_enabled": True,
            "rollout_percentage": 100,
        },
        {
            "name": "voicemail_sms",
            "display_name": "Voicemail SMS",
            "category": "notifications",
            "default_enabled": False,
            "rollout_percentage": 50,
        },
        {
            "name": "calendar_sync",
            "display_name": "Calendar Sync",
            "category": "integration",
            "default_enabled": False,
            "required_plan_tier": "starter",
            "rollout_percentage": 100,
        },
        {
            "name": "crm_integration",
            "display_name": "CRM Integration",
            "category": "integration",
            "default_enabled": False,
            "required_plan_tier": "pro",
            "rollout_percentage": 100,
        },
        {
            "name": "custom_ai_personality",
            "display_name": "Custom AI Personality",
            "category": "ai",
            "default_enabled": False,
            "required_plan_tier": "pro",
            "rollout_percentage": 100,
        },
        {
            "name": "multi_language",
            "display_name": "Multi-Language Support",
            "category": "ai",
            "default_enabled": False,
            "required_plan_tier": "pro",
            "rollout_percentage": 100,
        },
        {
            "name": "api_access",
            "display_name": "API Access",
            "category": "integration",
            "default_enabled": False,
            "required_plan_tier": "pro",
            "rollout_percentage": 100,
        },
        {
            "name": "analytics_advanced",
            "display_name": "Advanced Analytics",
            "category": "ui",
            "default_enabled": False,
            "required_plan_tier": "pro",
            "rollout_percentage": 100,
        },
        {
            "name": "call_transfer",
            "display_name": "Call Transfer",
            "category": "ai",
            "default_enabled": True,
            "rollout_percentage": 100,
        },
        {
            "name": "webhook_custom",
            "display_name": "Custom Webhooks",
            "category": "integration",
            "default_enabled": False,
            "required_plan_tier": "starter",
            "rollout_percentage": 100,
        },
        {
            "name": "ab_testing",
            "display_name": "A/B Testing",
            "category": "ai",
            "default_enabled": False,
            "required_plan_tier": "pro",
            "rollout_percentage": 100,
        },
        {
            "name": "priority_support",
            "display_name": "Priority Support",
            "category": "billing",
            "default_enabled": False,
            "required_plan_tier": "pro",
            "rollout_percentage": 100,
        },
    ]

    def __init__(self) -> None:
        self._flags: Dict[str, FeatureFlag] = {}
        self._overrides: Dict[str, Dict[str, FeatureFlagOverride]] = {}
        self._tenant_cache: Dict[str, Set[str]] = {}

        # Initialize built-in flags
        for flag_data in self.BUILT_IN_FLAGS:
            flag = FeatureFlag(**flag_data)
            self._flags[flag.name] = flag

    # -- Flag CRUD --------------------------------------------------------

    async def create_flag(
        self,
        name: str,
        display_name: str,
        description: Optional[str] = None,
        category: str = "general",
        default_enabled: bool = False,
        rollout_percentage: int = 100,
        required_plan_tier: Optional[str] = None,
    ) -> FeatureFlag:
        """Create a new feature flag."""
        if name in self._flags:
            raise ValueError(f"Feature flag '{name}' already exists")

        flag = FeatureFlag(
            name=name,
            display_name=display_name,
            description=description,
            category=category,
            default_enabled=default_enabled,
            rollout_percentage=rollout_percentage,
            required_plan_tier=required_plan_tier,
        )
        self._flags[name] = flag

        logger.info("feature_flag.created", name=name, category=category)
        return flag

    async def get_flag(self, name: str) -> Optional[FeatureFlag]:
        """Get a feature flag by name."""
        return self._flags.get(name)

    async def list_flags(
        self,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> List[FeatureFlag]:
        """List feature flags."""
        flags = list(self._flags.values())
        if category:
            flags = [f for f in flags if f.category == category]
        if active_only:
            flags = [f for f in flags if f.is_active]
        return sorted(flags, key=lambda f: f.display_name)

    async def update_flag(
        self,
        name: str,
        updates: Dict[str, Any],
    ) -> FeatureFlag:
        """Update a feature flag."""
        flag = self._flags.get(name)
        if not flag:
            raise ValueError(f"Feature flag '{name}' not found")

        for key, value in updates.items():
            if hasattr(flag, key):
                setattr(flag, key, value)

        flag.updated_at = datetime.utcnow()

        # Invalidate cache
        self._tenant_cache.clear()

        logger.info("feature_flag.updated", name=name, changes=list(updates.keys()))
        return flag

    async def delete_flag(self, name: str) -> None:
        """Soft-delete a feature flag."""
        flag = self._flags.get(name)
        if flag:
            flag.is_active = False
            flag.updated_at = datetime.utcnow()

        # Clear overrides for this flag
        for tenant_overrides in self._overrides.values():
            tenant_overrides.pop(name, None)

        self._tenant_cache.clear()
        logger.info("feature_flag.deactivated", name=name)

    # -- Per-Tenant Checks ------------------------------------------------

    async def is_enabled(
        self,
        flag_name: str,
        tenant_id: uuid.UUID,
        plan_tier: str = "free",
    ) -> bool:
        """Check if a feature flag is enabled for a tenant.

        Resolution order:
            1. Check explicit override
            2. Check plan requirement
            3. Check rollout percentage
            4. Use default

        Args:
            flag_name: Feature flag name
            tenant_id: Tenant ID
            plan_tier: Tenant's plan tier

        Returns:
            True if feature is enabled for this tenant
        """
        flag = self._flags.get(flag_name)
        if not flag or not flag.is_active:
            return False

        # 1. Check explicit override
        tenant_overrides = self._overrides.get(str(tenant_id), {})
        override = tenant_overrides.get(flag_name)
        if override and override.enabled is not None:
            return override.enabled

        # 2. Check plan requirement
        if flag.required_plan_tier:
            plan_hierarchy = {"free": 0, "starter": 1, "pro": 2, "enterprise": 3}
            flag_level = plan_hierarchy.get(flag.required_plan_tier, 999)
            tenant_level = plan_hierarchy.get(plan_tier, -1)
            if tenant_level < flag_level:
                return False

        # 3. Check rollout percentage
        if flag.rollout_percentage < 100:
            if not self._is_in_rollout(tenant_id, flag_name, flag.rollout_percentage):
                return flag.default_enabled

        # 4. Use default
        return flag.default_enabled

    def _is_in_rollout(
        self, tenant_id: uuid.UUID, flag_name: str, percentage: int
    ) -> bool:
        """Deterministically check if tenant is in rollout group.

        Uses hash of tenant_id + flag_name for consistent assignment.
        """
        hash_input = f"{tenant_id}:{flag_name}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100
        return bucket < percentage

    async def get_enabled_features(
        self,
        tenant_id: uuid.UUID,
        plan_tier: str = "free",
    ) -> Set[str]:
        """Get all enabled features for a tenant.

        Uses caching for repeated lookups.
        """
        cache_key = f"{tenant_id}:{plan_tier}"
        if cache_key in self._tenant_cache:
            return self._tenant_cache[cache_key]

        enabled = set()
        for flag in self._flags.values():
            if await self.is_enabled(flag.name, tenant_id, plan_tier):
                enabled.add(flag.name)

        self._tenant_cache[cache_key] = enabled
        return enabled

    async def check_multiple(
        self,
        flag_names: List[str],
        tenant_id: uuid.UUID,
        plan_tier: str = "free",
    ) -> Dict[str, bool]:
        """Check multiple feature flags at once."""
        return {
            name: await self.is_enabled(name, tenant_id, plan_tier)
            for name in flag_names
        }

    # -- Overrides --------------------------------------------------------

    async def set_override(
        self,
        tenant_id: uuid.UUID,
        flag_name: str,
        enabled: bool,
        set_by: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
    ) -> FeatureFlagOverride:
        """Set an explicit override for a tenant."""
        if flag_name not in self._flags:
            raise ValueError(f"Feature flag '{flag_name}' not found")

        tid = str(tenant_id)
        if tid not in self._overrides:
            self._overrides[tid] = {}

        override = FeatureFlagOverride(
            tenant_id=tenant_id,
            flag_name=flag_name,
            enabled=enabled,
            set_by=set_by,
            set_reason=reason,
        )
        self._overrides[tid][flag_name] = override

        # Invalidate cache
        self._tenant_cache = {
            k: v for k, v in self._tenant_cache.items()
            if not k.startswith(f"{tenant_id}:")
        }

        logger.info(
            "feature_flag.override_set",
            tenant_id=tid,
            flag=flag_name,
            enabled=enabled,
        )

        return override

    async def clear_override(
        self,
        tenant_id: uuid.UUID,
        flag_name: str,
    ) -> None:
        """Clear an explicit override for a tenant."""
        tid = str(tenant_id)
        if tid in self._overrides:
            self._overrides[tid].pop(flag_name, None)

        # Invalidate cache
        self._tenant_cache = {
            k: v for k, v in self._tenant_cache.items()
            if not k.startswith(f"{tenant_id}:")
        }

        logger.info("feature_flag.override_cleared", tenant_id=tid, flag=flag_name)

    async def get_override(
        self,
        tenant_id: uuid.UUID,
        flag_name: str,
    ) -> Optional[FeatureFlagOverride]:
        """Get an explicit override for a tenant."""
        return self._overrides.get(str(tenant_id), {}).get(flag_name)

    async def list_overrides(
        self,
        tenant_id: uuid.UUID,
    ) -> List[FeatureFlagOverride]:
        """List all overrides for a tenant."""
        return list(self._overrides.get(str(tenant_id), {}).values())

    # -- Tenant Feature Summary -------------------------------------------

    async def get_tenant_feature_summary(
        self,
        tenant_id: uuid.UUID,
        plan_tier: str = "free",
    ) -> List[Dict[str, Any]]:
        """Get full feature flag summary for a tenant."""
        overrides = self._overrides.get(str(tenant_id), {})
        summary = []

        for flag in self._flags.values():
            override = overrides.get(flag.name)
            is_enabled = await self.is_enabled(flag.name, tenant_id, plan_tier)

            summary.append({
                **flag.to_dict(),
                "enabled_for_tenant": is_enabled,
                "override_set": override is not None,
                "override_value": override.enabled if override else None,
            })

        return summary

    # -- Rollout Management -----------------------------------------------

    async def update_rollout(
        self,
        flag_name: str,
        percentage: int,
    ) -> FeatureFlag:
        """Update rollout percentage for a feature flag.

        Args:
            flag_name: Feature flag name
            percentage: 0-100 rollout percentage

        Returns:
            Updated feature flag
        """
        if not 0 <= percentage <= 100:
            raise ValueError("Rollout percentage must be between 0 and 100")

        flag = await self.update_flag(flag_name, {"rollout_percentage": percentage})

        logger.info(
            "feature_flag.rollout_updated",
            name=flag_name,
            percentage=percentage,
        )

        return flag

    async def increment_rollout(
        self,
        flag_name: str,
        increment: int = 10,
    ) -> FeatureFlag:
        """Gradually increase rollout percentage.

        Args:
            flag_name: Feature flag name
            increment: Percentage to add

        Returns:
            Updated feature flag
        """
        flag = self._flags.get(flag_name)
        if not flag:
            raise ValueError(f"Feature flag '{flag_name}' not found")

        new_percentage = min(100, flag.rollout_percentage + increment)
        return await self.update_rollout(flag_name, new_percentage)

    # -- Cache Management -------------------------------------------------

    def invalidate_cache(self, tenant_id: Optional[uuid.UUID] = None) -> None:
        """Invalidate feature flag cache.

        Args:
            tenant_id: If provided, only invalidate for this tenant.
        """
        if tenant_id:
            self._tenant_cache = {
                k: v for k, v in self._tenant_cache.items()
                if not k.startswith(f"{tenant_id}:")
            }
        else:
            self._tenant_cache.clear()

        logger.debug("feature_flag.cache_invalidated", tenant_id=str(tenant_id) if tenant_id else "all")
