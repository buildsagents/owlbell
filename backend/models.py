"""
Owlbell — Barrel Import for All Models.

Location: backend/models.py

This module imports and re-exports all SQLAlchemy models and enums
for convenient access by Alembic, admin tools, and other subsystems.

Usage:
    from backend.models import Base, Tenant, User, Call, CallStatus

Intended for:
- Alembic auto-detection (target_metadata)
- Admin dashboards
- Data export/import tools
- Interactive shells (ipython, Django-style)
"""

from __future__ import annotations

# ── Base ──────────────────────────────────────────────────────────
from backend.db.models.base import Base

# ── Enums (re-export all) ────────────────────────────────────────
from backend.db.models.enums import (
    AIModel,
    ActorType,
    AppointmentStatus,
    CallDirection,
    CallLegType,
    CallResult,
    CallStatus,
    DayOfWeek,
    IntegrationProvider,
    IntegrationType,
    IntentType,
    MessageRole,
    MessageStatus,
    MessageType,
    NotificationChannel,
    PlanTier,
    PlanType,
    RoutingAction,
    RoutingRuleType,
    RoutingType,
    TenantStatus,
    TranscriptSource,
    UserRole,
    VoiceType,
    WebhookEvent,
)

# ── Core Models ───────────────────────────────────────────────────
from backend.db.models.tenant import Tenant, TenantConfig
from backend.db.models.user import User
from backend.db.models.call import Call, CallLeg, Recording

# ── AI Models ─────────────────────────────────────────────────────
from backend.db.models.ai import (
    Conversation,
    Message,
    Prompt,
    ToolCall,
    Transcript,
)

# ── Business Models ───────────────────────────────────────────────
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

# ── Integration Models ────────────────────────────────────────────
from backend.db.models.integration import (
    IntegrationConnection,
    OAuthToken,
    SyncLog,
    WebhookEndpoint,
)

# ── Operations Models ─────────────────────────────────────────────
from backend.db.models.operations import (
    AuditLog,
    PlanDefinition,
    UsageRecord,
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
    "Conversation",
    "Message",
    "Prompt",
    "ToolCall",
    "Transcript",
    # Business
    "Appointment",
    "BusinessHours",
    "CallerProfile",
    "CallSummary",
    "FAQEntry",
    "HolidaySchedule",
    "NotificationLog",
    "RoutingRule",
    # Integration
    "IntegrationConnection",
    "OAuthToken",
    "SyncLog",
    "WebhookEndpoint",
    # Operations
    "AuditLog",
    "PlanDefinition",
    "UsageRecord",
    # Enums - Call
    "CallDirection",
    "CallStatus",
    "CallResult",
    "CallLegType",
    # Enums - Message/Conversation
    "MessageRole",
    "MessageType",
    "MessageStatus",
    # Enums - Appointment
    "AppointmentStatus",
    # Enums - Routing
    "RoutingType",
    "RoutingRuleType",
    "RoutingAction",
    # Enums - Webhook/Notification
    "WebhookEvent",
    "NotificationChannel",
    # Enums - Integration
    "IntegrationProvider",
    "IntegrationType",
    # Enums - Plan/Billing
    "PlanTier",
    "PlanType",
    # Enums - User/Tenant
    "UserRole",
    "TenantStatus",
    # Enums - Calendar
    "DayOfWeek",
    # Enums - AI/Pipeline
    "AIModel",
    "VoiceType",
    "TranscriptSource",
    "IntentType",
    # Enums - Audit
    "ActorType",
]
