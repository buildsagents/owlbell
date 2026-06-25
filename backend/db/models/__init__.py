"""
SQLAlchemy model registry.

Location: backend/db/models/__init__.py

Import all models here for Alembic auto-detection and clean imports.
The ``Base`` metadata is the target for Alembic migrations.
"""

from backend.db.models.base import Base
from backend.db.models.tenant import Tenant, TenantConfig
from backend.db.models.user import User
from backend.db.models.call import Call, CallLeg, Recording
from backend.db.models.ai import (
    Conversation,
    Message,
    Prompt,
    ToolCall,
    Transcript,
)
from backend.db.models.business import (
    Appointment,
    BusinessHours,
    CallerProfile,
    CallSummary,
    FAQEntry,
    HolidaySchedule,
    NotificationLog,
    RoutingRule,
)
from backend.db.models.integration import (
    IntegrationConnection,
    OAuthToken,
    SyncLog,
    WebhookEndpoint,
)
from backend.db.models.operations import (
    AuditLog,
    PlanDefinition,
    UsageRecord,
)
from backend.db.models.prompts import (
    PromptABTestRecord,
    PromptVersionRecord,
)
from backend.db.models.onboarding import (
    OnboardingEmailRecord,
    OnboardingPipelineRecord,
    OnboardingStepRecord,
)

__all__ = [
    # Base
    "Base",
    # Core
    "Tenant",
    "TenantConfig",
    "User",
    # Calls
    "Call",
    "CallLeg",
    "Recording",
    # AI
    "Transcript",
    "Conversation",
    "Message",
    "Prompt",
    "ToolCall",
    # Business
    "Appointment",
    "RoutingRule",
    "FAQEntry",
    "BusinessHours",
    "HolidaySchedule",
    "CallerProfile",
    "CallSummary",
    "NotificationLog",
    # Integration
    "IntegrationConnection",
    "OAuthToken",
    "WebhookEndpoint",
    "SyncLog",
    # Operations
    "UsageRecord",
    "AuditLog",
    "PlanDefinition",
    # Prompts
    "PromptVersionRecord",
    "PromptABTestRecord",
    # Onboarding
    "OnboardingPipelineRecord",
    "OnboardingStepRecord",
    "OnboardingEmailRecord",
]
