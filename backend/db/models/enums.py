"""
Shared enum definitions used across models, APIs, and the database layer.

Location: backend/db/models/enums.py

All enums are defined as ``str``-backed Python enums so they serialize
naturally to JSON and can be used directly in SQLAlchemy ``Enum`` columns.

These enums map to PostgreSQL native enum types created via Alembic
migrations for data integrity at the database level.
"""

from __future__ import annotations

import enum


# ── Call Enums ────────────────────────────────────────────────────


class CallDirection(str, enum.Enum):
    """Direction of a phone call."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, enum.Enum):
    """Lifecycle status of a call."""

    QUEUED = "queued"
    RINGING = "ringing"
    ANSWERED = "answered"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    TRANSFERRED = "transferred"
    COMPLETED = "completed"
    FAILED = "failed"
    VOICEMAIL = "voicemail"
    NO_ANSWER = "no_answer"


class CallResult(str, enum.Enum):
    """Final disposition / result of a completed call."""

    SUCCESS = "success"
    VOICEMAIL_LEFT = "voicemail_left"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    TRANSFERRED = "transferred"
    HANGUP = "hangup"
    ERROR = "error"


class CallLegType(str, enum.Enum):
    """Type of participant (leg) in a call."""

    CALLER = "caller"
    AI_AGENT = "ai_agent"
    HUMAN_AGENT = "human_agent"
    VOICEMAIL = "voicemail"
    CONFERENCE = "conference"


# ── Message / Conversation Enums ──────────────────────────────────


class MessageRole(str, enum.Enum):
    """Role of a participant in an AI conversation message."""

    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"
    TOOL = "tool"


class MessageType(str, enum.Enum):
    """Type/category of a conversation message."""

    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TRANSFER = "transfer"
    VOICEMAIL = "voicemail"
    HANGUP = "hangup"


class MessageStatus(str, enum.Enum):
    """Processing status of a message (for async pipelines)."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Appointment Enums ─────────────────────────────────────────────


class AppointmentStatus(str, enum.Enum):
    """Status of an appointment booking."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


# ── Routing Enums ─────────────────────────────────────────────────


class RoutingType(str, enum.Enum):
    """Type of call routing rule."""

    AUTO_ATTENDANT = "auto_attendant"
    TIME_BASED = "time_based"
    INTENT_BASED = "intent_based"
    CALLER_ID = "caller_id"
    DEFAULT = "default"


class RoutingRuleType(str, enum.Enum):
    """Alias for RoutingType — used in API schemas."""

    AUTO_ATTENDANT = "auto_attendant"
    TIME_BASED = "time_based"
    INTENT_BASED = "intent_based"
    CALLER_ID = "caller_id"
    DEFAULT = "default"


class RoutingAction(str, enum.Enum):
    """Action taken when a routing rule matches."""

    ANSWER = "answer"
    TRANSFER = "transfer"
    VOICEMAIL = "voicemail"
    REJECT = "reject"
    QUEUE = "queue"
    MENU = "menu"


# ── Webhook / Notification Enums ──────────────────────────────────


class WebhookEvent(str, enum.Enum):
    """Events that can trigger webhook notifications."""

    CALL_STARTED = "call.started"
    CALL_ENDED = "call.ended"
    CALL_TRANSCRIBED = "call.transcribed"
    APPOINTMENT_CREATED = "appointment.created"
    APPOINTMENT_UPDATED = "appointment.updated"
    VOICEMAIL_RECEIVED = "voicemail.received"
    MESSAGE_RECEIVED = "message.received"


class NotificationChannel(str, enum.Enum):
    """Channel for delivering notifications."""

    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    SLACK = "slack"
    PUSH = "push"
    IN_APP = "in_app"


# ── Integration Enums ─────────────────────────────────────────────


class IntegrationProvider(str, enum.Enum):
    """Third-party integration providers."""

    GOOGLE_CALENDAR = "google_calendar"
    OUTLOOK_CALENDAR = "outlook_calendar"
    ZAPIER = "zapier"
    MAKE = "make"
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    SLACK = "slack"
    TEAMS = "teams"


class IntegrationType(str, enum.Enum):
    """Alias for IntegrationProvider — used in API schemas."""

    GOOGLE_CALENDAR = "google_calendar"
    OUTLOOK_CALENDAR = "outlook_calendar"
    ZAPIER = "zapier"
    MAKE = "make"
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    SLACK = "slack"
    TEAMS = "teams"


# ── Plan / Billing Enums ──────────────────────────────────────────


class PlanTier(str, enum.Enum):
    """Subscription plan tiers."""

    FREE = "free"
    BASIC = "basic"
    STARTER = "starter"
    PRO = "pro"
    PRO_PLUS = "pro_plus"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class PlanType(str, enum.Enum):
    """Alias for PlanTier — used in API schemas."""

    FREE = "free"
    BASIC = "basic"
    STARTER = "starter"
    PRO = "pro"
    PRO_PLUS = "pro_plus"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# ── User / Tenant Enums ───────────────────────────────────────────


class UserRole(str, enum.Enum):
    """Roles for staff members within a tenant."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    AGENT = "agent"
    VIEWER = "viewer"


class TenantStatus(str, enum.Enum):
    """Lifecycle status of a tenant account."""

    PENDING = "pending"
    ACTIVE = "active"
    LIMITED = "limited"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    PURGED = "purged"


# ── Calendar / Scheduling Enums ───────────────────────────────────


class DayOfWeek(str, enum.Enum):
    """Days of the week for business hours and scheduling."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


# ── AI / Pipeline Enums ───────────────────────────────────────────


class AIModel(str, enum.Enum):
    """Available AI / LLM models."""

    LLAMA3_8B = "llama3.1:8b"
    LLAMA3_70B = "llama3.1:70b"
    MISTRAL_7B = "mistral:7b"
    MIXTRAL_8X7B = "mixtral:8x7b"
    CUSTOM = "custom"
    RETELL_AI = "retell_ai"


class VoiceType(str, enum.Enum):
    """Text-to-speech voice options."""

    PIPER_DEFAULT = "piper_default"
    PIPER_MALE_1 = "piper_male_1"
    PIPER_FEMALE_1 = "piper_female_1"
    PIPER_CUSTOM = "piper_custom"


class TranscriptSource(str, enum.Enum):
    """Speech-to-text engine providers."""

    WHISPER_LOCAL = "whisper_local"
    WHISPER_API = "whisper_api"
    DEEPGRAM = "deepgram"
    ASSEMBLY = "assembly"
    RETELL_AI = "retell_ai"


class IntentType(str, enum.Enum):
    """Types of caller intents detected by the AI."""

    APPOINTMENT = "appointment"
    QUESTION = "question"
    COMPLAINT = "complaint"
    TRANSFER = "transfer_request"
    VOICEMAIL = "voicemail_request"
    INFORMATION = "information"
    EMERGENCY = "emergency"
    SALES = "sales"
    SUPPORT = "support"
    GENERAL = "general"


# ── Actor / Audit Enums ───────────────────────────────────────────


class ActorType(str, enum.Enum):
    """Types of actors that can perform actions in the system."""

    USER = "user"
    SYSTEM = "system"
    API_KEY = "api_key"
    AI_AGENT = "ai_agent"
    INTEGRATION = "integration"
