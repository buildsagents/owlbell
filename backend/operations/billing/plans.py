"""operations/billing/plans.py - Plan definitions and limit enforcement.

Defines plan tiers, their limits, and provides utilities for
enforcing plan-based restrictions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class PlanTier(str, Enum):
    """Available plan tiers."""
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class PlanLimits:
    """Immutable plan limits configuration."""
    tier: PlanTier
    name: str
    description: str
    monthly_price_usd: float
    annual_price_usd: float

    # Usage limits
    max_calls_monthly: int
    max_concurrent_calls: int
    max_minutes_monthly: int  # 0 = unlimited
    max_users: int
    max_phone_numbers: int
    max_call_duration_minutes: int

    # AI tier
    ai_model_tier: str  # "fast", "quality", "premium"

    # Features
    included_features: frozenset[str] = field(default_factory=frozenset)

    # Overage
    overage_price_per_call: float = 0.0
    overage_price_per_minute: float = 0.0
    overage_price_per_1k_tokens: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "name": self.name,
            "description": self.description,
            "monthly_price_usd": self.monthly_price_usd,
            "annual_price_usd": self.annual_price_usd,
            "max_calls_monthly": self.max_calls_monthly,
            "max_concurrent_calls": self.max_concurrent_calls,
            "max_minutes_monthly": self.max_minutes_monthly,
            "max_users": self.max_users,
            "max_phone_numbers": self.max_phone_numbers,
            "ai_model_tier": self.ai_model_tier,
            "max_call_duration_minutes": self.max_call_duration_minutes,
            "included_features": sorted(self.included_features),
            "overage_price_per_call": self.overage_price_per_call,
            "overage_price_per_minute": self.overage_price_per_minute,
        }


# -- Plan Definitions -----------------------------------------------------

FREE_PLAN = PlanLimits(
    tier=PlanTier.FREE,
    name="Free",
    description="Perfect for trying out Owlbell. 100 calls per month.",
    monthly_price_usd=0.0,
    annual_price_usd=0.0,
    max_calls_monthly=100,
    max_concurrent_calls=1,
    max_minutes_monthly=0,
    max_users=1,
    max_phone_numbers=1,
    max_call_duration_minutes=10,
    ai_model_tier="fast",
    included_features=frozenset({
        "basic_ai",
        "call_transcription",
        "voicemail",
        "web_dashboard",
    }),
)

STARTER_PLAN = PlanLimits(
    tier=PlanTier.STARTER,
    name="Starter",
    description="For small businesses. 500 calls per month, quality AI.",
    monthly_price_usd=29.0,
    annual_price_usd=290.0,
    max_calls_monthly=500,
    max_concurrent_calls=3,
    max_minutes_monthly=0,
    max_users=5,
    max_phone_numbers=3,
    max_call_duration_minutes=30,
    ai_model_tier="quality",
    included_features=frozenset({
        "basic_ai",
        "call_transcription",
        "voicemail",
        "web_dashboard",
        "sms_notifications",
        "calendar_sync",
        "custom_greeting",
        "call_transfer",
        "analytics_basic",
    }),
)

PRO_PLAN = PlanLimits(
    tier=PlanTier.PRO,
    name="Pro",
    description="For growing businesses. 2000 calls per month, premium AI.",
    monthly_price_usd=79.0,
    annual_price_usd=790.0,
    max_calls_monthly=2000,
    max_concurrent_calls=10,
    max_minutes_monthly=0,
    max_users=20,
    max_phone_numbers=10,
    max_call_duration_minutes=60,
    ai_model_tier="premium",
    included_features=frozenset({
        "basic_ai",
        "call_transcription",
        "voicemail",
        "web_dashboard",
        "sms_notifications",
        "calendar_sync",
        "custom_greeting",
        "call_transfer",
        "analytics_basic",
        "analytics_advanced",
        "crm_integration",
        "multi_language",
        "custom_ai_personality",
        "priority_support",
        "api_access",
    }),
)

ENTERPRISE_PLAN = PlanLimits(
    tier=PlanTier.ENTERPRISE,
    name="Enterprise",
    description="Custom solution for large organizations.",
    monthly_price_usd=0.0,
    annual_price_usd=0.0,
    max_calls_monthly=10000,
    max_concurrent_calls=50,
    max_minutes_monthly=0,
    max_users=100,
    max_phone_numbers=50,
    max_call_duration_minutes=120,
    ai_model_tier="premium",
    included_features=frozenset({
        "basic_ai",
        "call_transcription",
        "voicemail",
        "web_dashboard",
        "sms_notifications",
        "calendar_sync",
        "custom_greeting",
        "call_transfer",
        "analytics_basic",
        "analytics_advanced",
        "crm_integration",
        "multi_language",
        "custom_ai_personality",
        "priority_support",
        "api_access",
        "dedicated_infrastructure",
        "custom_model",
        "sla_guarantee",
        "white_label",
    }),
)

PLAN_MAP: Dict[str, PlanLimits] = {
    "free": FREE_PLAN,
    "starter": STARTER_PLAN,
    "pro": PRO_PLAN,
    "enterprise": ENTERPRISE_PLAN,
}


# -- Plan Manager ---------------------------------------------------------


class PlanManager:
    """Manages plan definitions and limit enforcement.

    Usage:
        manager = PlanManager()
        plan = manager.get_plan("starter")
        is_allowed = manager.is_feature_allowed("starter", "api_access")
    """

    def __init__(self, custom_plans: Optional[Dict[str, PlanLimits]] = None):
        self._plans = {**PLAN_MAP}
        if custom_plans:
            self._plans.update(custom_plans)

    def get_plan(self, tier: str) -> PlanLimits:
        """Get plan limits by tier name.

        Args:
            tier: Plan tier string (free, starter, pro, enterprise)

        Returns:
            PlanLimits for the given tier

        Raises:
            ValueError: If tier is not recognized
        """
        plan = self._plans.get(tier.lower())
        if not plan:
            raise ValueError(f"Unknown plan tier: {tier}")
        return plan

    def list_plans(self) -> List[PlanLimits]:
        """List all available plans."""
        return list(self._plans.values())

    def is_feature_allowed(self, tier: str, feature: str) -> bool:
        """Check if a feature is allowed for a given plan tier."""
        try:
            plan = self.get_plan(tier)
            return feature in plan.included_features
        except ValueError:
            return False

    def get_feature_list(self, tier: str) -> List[str]:
        """Get list of features available for a plan tier."""
        try:
            plan = self.get_plan(tier)
            return sorted(plan.included_features)
        except ValueError:
            return []

    def check_limit(self, tier: str, limit_type: str, current_value: int) -> tuple[bool, int]:
        """Check if current usage is within plan limit.

        Returns:
            Tuple of (is_within_limit, remaining)
        """
        try:
            plan = self.get_plan(tier)
            limit = getattr(plan, limit_type, 0)
            if limit == 0:  # Unlimited
                return True, -1
            remaining = limit - current_value
            return remaining > 0, remaining
        except ValueError:
            return False, 0

    def get_overage_cost(self, tier: str, calls_over: int = 0, minutes_over: float = 0.0) -> float:
        """Calculate estimated overage cost."""
        try:
            plan = self.get_plan(tier)
            cost = 0.0
            cost += calls_over * plan.overage_price_per_call
            cost += minutes_over * plan.overage_price_per_minute
            return round(cost, 2)
        except ValueError:
            return 0.0

    def compare_plans(self) -> List[Dict[str, Any]]:
        """Generate plan comparison data."""
        return [plan.to_dict() for plan in self._plans.values()]

    def get_plan_for_usage(self, calls_monthly: int) -> str:
        """Recommend plan based on usage."""
        if calls_monthly <= FREE_PLAN.max_calls_monthly:
            return "free"
        elif calls_monthly <= STARTER_PLAN.max_calls_monthly:
            return "starter"
        elif calls_monthly <= PRO_PLAN.max_calls_monthly:
            return "pro"
        else:
            return "enterprise"
