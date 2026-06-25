"""
Owlbell — Demo Data Seeding.

Location: backend/db/seed_data.py

Comprehensive, idempotent seed data for Owlbell. When a developer
runs the system for the first time they get a fully populated "Smith Dental
Clinic" demo tenant so every feature is immediately explorable.

Usage (via CLI wrapper in backend/db/seed.py):
    python -m backend.db.seed --demo       # Seed demo data
    python -m backend.db.seed --reset      # Truncate + re-seed

Design principles
-----------------
* **Idempotent** — can be run N times safely; existing rows are skipped.
* **Self-contained** — only needs a SQLAlchemy async session.
* **Realistic** — sample calls/conversations mirror genuine dental-office
  traffic patterns.
* **Fast** — uses bulk inserts where possible; completes in < 2 s on a
  modest laptop.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    Appointment,
    AuditLog,
    BusinessHours,
    Call,
    CallLeg,
    CallerProfile,
    CallResult,
    CallStatus,
    CallSummary,
    Conversation,
    FAQEntry,
    HolidaySchedule,
    Message,
    NotificationLog,
    PlanDefinition,
    Prompt,
    Recording,
    RoutingRule,
    Tenant,
    TenantConfig,
    Transcript,
    UsageRecord,
    User,
)
from backend.db.models.enums import (
    AIModel,
    AppointmentStatus,
    CallDirection,
    DayOfWeek,
    NotificationChannel,
    PlanTier,
    RoutingAction,
    RoutingType,
    TenantStatus,
    TranscriptSource,
    UserRole,
    VoiceType,
)

logger = logging.getLogger("seed_data")

# ---------------------------------------------------------------------------
# Hard-coded UUIDs for idempotency — same seed data every run.
# ---------------------------------------------------------------------------

_DEMO_TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
_DEMO_USER_ID = UUID("22222222-2222-2222-2222-222222222222")
_DEMO_PLAN_IDS: Dict[PlanTier, UUID] = {
    PlanTier.FREE: UUID("33333333-3333-3333-3333-333333333333"),
    PlanTier.STARTER: UUID("44444444-4444-4444-4444-444444444444"),
    PlanTier.PROFESSIONAL: UUID("55555555-5555-5555-5555-555555555555"),
}

_CALL_IDS: List[UUID] = [UUID(f"66666666-6666-6666-6666-{i:012d}") for i in range(1, 11)]
_APT_IDS: List[UUID] = [UUID(f"77777777-7777-7777-7777-{i:012d}") for i in range(1, 6)]
_PROMPT_IDS: List[UUID] = [UUID(f"88888888-8888-8888-8888-{i:012d}") for i in range(1, 6)]
_RULE_IDS: List[UUID] = [UUID(f"99999999-9999-9999-9999-{i:012d}") for i in range(1, 6)]

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _sha256_phone(phone: str) -> str:
    """Return SHA-256 hash of a normalized phone number."""
    normalized = phone.replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    return hashlib.sha256(normalized.encode()).hexdigest()


async def _get_or_create_tenant(db: AsyncSession, slug: str) -> Optional[UUID]:
    """Return tenant ID if it already exists, else None."""
    result = await db.execute(select(Tenant.id).where(Tenant.slug == slug))
    row = result.scalar_one_or_none()
    return row


async def _tenant_exists(db: AsyncSession, tenant_id: UUID) -> bool:
    """Check whether a tenant with the given UUID exists."""
    result = await db.execute(select(Tenant.id).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# 1. Plan Definitions
# ---------------------------------------------------------------------------

PLAN_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "id": _DEMO_PLAN_IDS[PlanTier.FREE],
        "plan_tier": PlanTier.FREE,
        "display_name": "Free",
        "description": "Perfect for small businesses trying AI answering. 100 minutes/month.",
        "max_minutes_monthly": 100,
        "max_concurrent_calls": 1,
        "max_users": 2,
        "max_phone_numbers": 1,
        "features_json": {
            "ai_answering": True,
            "call_transcription": True,
            "voicemail": True,
            "basic_routing": True,
            "email_notifications": True,
            "sms_notifications": False,
            "calendar_sync": False,
            "crm_sync": False,
            "custom_prompts": False,
            "analytics_dashboard": False,
            "webhook_events": False,
            "priority_support": False,
        },
        "is_public": True,
        "sort_order": 1,
    },
    {
        "id": _DEMO_PLAN_IDS[PlanTier.STARTER],
        "plan_tier": PlanTier.STARTER,
        "display_name": "Starter",
        "description": "For growing businesses. 500 minutes/month, 5 users, calendar sync.",
        "max_minutes_monthly": 500,
        "max_concurrent_calls": 3,
        "max_users": 5,
        "max_phone_numbers": 2,
        "features_json": {
            "ai_answering": True,
            "call_transcription": True,
            "voicemail": True,
            "basic_routing": True,
            "email_notifications": True,
            "sms_notifications": True,
            "calendar_sync": True,
            "crm_sync": False,
            "custom_prompts": True,
            "analytics_dashboard": True,
            "webhook_events": True,
            "priority_support": False,
        },
        "is_public": True,
        "sort_order": 2,
    },
    {
        "id": _DEMO_PLAN_IDS[PlanTier.PROFESSIONAL],
        "plan_tier": PlanTier.PROFESSIONAL,
        "display_name": "Professional",
        "description": "Full-featured. 2,000 minutes/month, 20 users, CRM, advanced analytics.",
        "max_minutes_monthly": 2000,
        "max_concurrent_calls": 10,
        "max_users": 20,
        "max_phone_numbers": 5,
        "features_json": {
            "ai_answering": True,
            "call_transcription": True,
            "voicemail": True,
            "basic_routing": True,
            "email_notifications": True,
            "sms_notifications": True,
            "calendar_sync": True,
            "crm_sync": True,
            "custom_prompts": True,
            "analytics_dashboard": True,
            "webhook_events": True,
            "priority_support": True,
            "dedicated_ai_model": True,
            "multi_language": True,
            "custom_voice": True,
        },
        "is_public": True,
        "sort_order": 3,
    },
]


async def seed_plan_definitions(db: AsyncSession) -> None:
    """Insert plan definitions if they do not already exist."""
    for plan_data in PLAN_DEFINITIONS:
        result = await db.execute(
            select(PlanDefinition.id).where(
                PlanDefinition.plan_tier == plan_data["plan_tier"]
            )
        )
        if result.scalar_one_or_none() is None:
            plan = PlanDefinition(**plan_data)
            db.add(plan)
            logger.info("seed.plan_created", tier=plan_data["plan_tier"].value)
        else:
            logger.debug("seed.plan_exists", tier=plan_data["plan_tier"].value)
    await db.flush()


# ---------------------------------------------------------------------------
# 2. Demo Tenant — "Smith Dental Clinic"
# ---------------------------------------------------------------------------

DEMO_TENANT_DATA = {
    "id": _DEMO_TENANT_ID,
    "slug": "smith-dental",
    "name": "Smith Dental Clinic",
    "status": TenantStatus.ACTIVE,
    "plan_tier": PlanTier.STARTER,
    # Business Profile
    "business_name": "Smith Dental Clinic",
    "business_phone": "+1-555-0100",
    "business_email": "frontdesk@smithdental.example.com",
    "business_timezone": "America/New_York",
    "business_address": "123 Maple Street, Suite 200, Springfield, IL 62701",
    "business_website": "https://www.smithdental.example.com",
    "industry": "healthcare",
    # AI Configuration
    "ai_model": AIModel.LLAMA3_8B,
    "ai_temperature": 0.7,
    "ai_max_tokens": 256,
    "ai_system_prompt": (
        "You are a professional, friendly dental receptionist at Smith Dental Clinic. "
        "You answer calls warmly, help patients schedule appointments, answer common "
        "questions, and take messages. Always be courteous, concise, and reassuring. "
        "If a caller has an emergency, triage quickly and offer to transfer to the "
        "emergency line."
    ),
    "voice_type": VoiceType.PIPER_FEMALE_1,
    "voice_speed": 1.0,
    "stt_model": TranscriptSource.WHISPER_LOCAL,
    "stt_language": "en",
    # Call Handling
    "max_call_duration": 600,
    "voicemail_enabled": True,
    "voicemail_greeting": (
        "Thank you for calling Smith Dental Clinic. We are unavailable right now. "
        "Please leave your name, phone number, and a brief message after the tone. "
        "We will return your call as soon as possible."
    ),
    "after_hours_action": "voicemail",
    "concurrent_calls_max": 3,
    # Customization
    "greeting_message": (
        "Thank you for calling Smith Dental Clinic. This is Alex, your virtual "
        "receptionist. How may I help you today?"
    ),
    "hold_music_url": "https://assets.owlbell.xyz/hold-music/classical-piano.mp3",
    "transfer_number": "+1-555-0199",
    # Metadata
    "config_json": {
        "timezone": "America/New_York",
        "language": "en",
        "call_recording_enabled": True,
        "recording_retention_days": 90,
        "transcript_retention_days": 365,
        "auto_tag_calls": True,
        "default_tags": ["dental", "patient"],
    },
    "features_json": {
        "appointment_booking": True,
        "insurance_verification": True,
        "new_patient_intake": True,
        "emergency_triage": True,
        "reminder_calls": True,
    },
}


async def seed_demo_tenant(db: AsyncSession) -> UUID:
    """Create the demo tenant if it does not exist. Returns tenant_id."""
    tenant_id = DEMO_TENANT_DATA["id"]
    existing = await _tenant_exists(db, tenant_id)
    if existing:
        logger.info("seed.demo_tenant_exists", tenant_id=str(tenant_id))
        return tenant_id

    tenant = Tenant(**DEMO_TENANT_DATA)
    db.add(tenant)
    await db.flush()

    # Tenant config (routing, notifications, integrations)
    config = TenantConfig(
        tenant_id=tenant_id,
        ai_settings={
            "voice_id": "piper_female_1",
            "speech_rate": 1.0,
            "greeting": DEMO_TENANT_DATA["greeting_message"],
            "language": "en",
            "hold_music": DEMO_TENANT_DATA["hold_music_url"],
            "timeout_handling": "offer_voicemail",
            "max_hold_seconds": 120,
        },
        routing_rules={
            "business_hours_only": False,
            "after_hours_action": "voicemail",
            "overflow_action": "ai_agent",
            "emergency_transfer_number": "+1-555-0199",
        },
        notification_settings={
            "email_summary": True,
            "email_recipient": "frontdesk@smithdental.example.com",
            "sms_summary": False,
            "daily_digest": True,
            "missed_call_alert": True,
            "appointment_confirmation": True,
            "new_patient_alert": True,
        },
        integrations={
            "google_calendar": {"enabled": False},
            "slack": {"enabled": False},
            "hubspot": {"enabled": False},
        },
    )
    db.add(config)
    await db.flush()

    logger.info("seed.demo_tenant_created", tenant_id=str(tenant_id), slug="smith-dental")
    return tenant_id


# ---------------------------------------------------------------------------
# 3. Demo User — Dr. Smith (owner)
# ---------------------------------------------------------------------------

DEMO_USER_DATA = {
    "id": _DEMO_USER_ID,
    "tenant_id": _DEMO_TENANT_ID,
    "email": "dr.smith@smithdental.example.com",
    # bcrypt hash for "DemoPass123!" — pre-computed so we don't need bcrypt in seed
    "password_hash": (
        "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA.qGZvKG6G"
    ),
    "first_name": "Dr. Sarah",
    "last_name": "Smith",
    "role": UserRole.ADMIN,
    "phone": "+1-555-0101",
    "avatar_url": "https://assets.owlbell.xyz/avatars/dr-sarah-smith.jpg",
    "is_active": True,
    "email_verified_at": datetime(2024, 1, 15, 10, 0, 0),
    "timezone": "America/New_York",
    "notification_prefs": {
        "email_call_summary": True,
        "email_voicemail": True,
        "email_appointment": True,
        "sms_call_summary": False,
        "dashboard_sound": True,
    },
}


async def seed_demo_user(db: AsyncSession, tenant_id: UUID) -> None:
    """Create the demo user (owner) for the tenant."""
    result = await db.execute(select(User.id).where(User.id == _DEMO_USER_ID))
    if result.scalar_one_or_none():
        logger.debug("seed.demo_user_exists", user_id=str(_DEMO_USER_ID))
        return

    user = User(**DEMO_USER_DATA)
    db.add(user)
    await db.flush()
    logger.info("seed.demo_user_created", user_id=str(_DEMO_USER_ID), email=user.email)


# ---------------------------------------------------------------------------
# 4. FAQ Entries — 10 common dental questions
# ---------------------------------------------------------------------------

FAQ_ENTRIES: List[Dict[str, Any]] = [
    {
        "id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000001"),
        "tenant_id": _DEMO_TENANT_ID,
        "question": "What are your office hours?",
        "answer": (
            "Our office hours are Monday through Friday from 9:00 AM to 5:00 PM, "
            "and Saturday from 9:00 AM to 1:00 PM. We are closed on Sundays and "
            "major holidays. If you have an emergency outside these hours, please "
            "press 0 to be transferred to our emergency line."
        ),
        "category": "hours",
        "tags_json": ["hours", "schedule", "availability"],
        "question_variants_json": [
            "When are you open?",
            "What time do you close?",
            "Are you open on weekends?",
            "How late are you open?",
        ],
    },
    {
        "id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000002"),
        "tenant_id": _DEMO_TENANT_ID,
        "question": "Do you take insurance?",
        "answer": (
            "Yes, we accept most major dental insurance plans including Delta Dental, "
            "Cigna, MetLife, Aetna, and UnitedHealthcare. We also offer flexible "
            "payment plans for uninsured patients. Please bring your insurance card "
            "to your appointment and we will verify your benefits before treatment."
        ),
        "category": "insurance",
        "tags_json": ["insurance", "payment", "coverage"],
        "question_variants_json": [
            "What insurance do you accept?",
            "Are you in-network with Delta Dental?",
            "Do you accept my insurance?",
            "Can you bill my insurance directly?",
        ],
    },
    {
        "id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000003"),
        "tenant_id": _DEMO_TENANT_ID,
        "question": "How do I schedule an appointment?",
        "answer": (
            "You can schedule an appointment right now over the phone with me. "
            "Just let me know what type of visit you need — routine cleaning, "
            "consultation, or a specific procedure — and I can check availability. "
            "You can also schedule online through our patient portal or by calling "
            "our front desk during business hours."
        ),
        "category": "scheduling",
        "tags_json": ["appointment", "scheduling", "booking"],
        "question_variants_json": [
            "Can I book a cleaning?",
            "I need to make an appointment",
            "How do I book online?",
            "Can I schedule for next week?",
        ],
    },
    {
        "id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000004"),
        "tenant_id": _DEMO_TENANT_ID,
        "question": "What should I do in a dental emergency?",
        "answer": (
            "If you are experiencing a dental emergency such as severe pain, a "
            "knocked-out tooth, or significant bleeding, please call us immediately. "
            "If it is during office hours we will see you as soon as possible. "
            "After hours, press 0 to be transferred to our 24/7 emergency line. "
            "For life-threatening situations, please call 911 or go to the nearest "
            "emergency room."
        ),
        "category": "emergency",
        "tags_json": ["emergency", "urgent", "pain", "after-hours"],
        "question_variants_json": [
            "I have a toothache",
            "My tooth got knocked out",
            "I am in severe pain",
            "Is this an emergency?",
            "Do you have an emergency dentist?",
        ],
    },
    {
        "id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000005"),
        "tenant_id": _DEMO_TENANT_ID,
        "question": "Do you offer teeth whitening?",
        "answer": (
            "Yes, we offer professional teeth whitening services. We provide both "
            "in-office treatments that can lighten your smile by several shades in "
            "a single visit, and take-home whitening kits with custom trays. "
            "Consultations are recommended to determine the best option for you. "
            "Would you like me to schedule a whitening consultation?"
        ),
        "category": "services",
        "tags_json": ["whitening", "cosmetic", "services"],
        "question_variants_json": [
            "Can you whiten my teeth?",
            "How much is teeth whitening?",
            "Do you do bleaching?",
            "What whitening options do you have?",
        ],
    },
    {
        "id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000006"),
        "tenant_id": _DEMO_TENANT_ID,
        "question": "How often should I get a cleaning?",
        "answer": (
            "We recommend professional cleanings every six months for most patients. "
            "However, if you have gum disease or are prone to cavities, we may "
            "recommend cleanings every three to four months. Dr. Smith will "
            "personalize your recall schedule based on your oral health needs."
        ),
        "category": "preventive",
        "tags_json": ["cleaning", "prevention", "hygiene"],
        "question_variants_json": [
            "When should I come back for a cleaning?",
            "How frequently do I need cleanings?",
            "Is once a year enough for a cleaning?",
        ],
    },
    {
        "id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000007"),
        "tenant_id": _DEMO_TENANT_ID,
        "question": "Do you see children?",
        "answer": (
            "Yes, we welcome patients of all ages! Dr. Smith has extensive experience "
            "with pediatric dentistry. We recommend a child's first dental visit by "
            "their first birthday or within six months of their first tooth appearing. "
            "Our office is designed to be kid-friendly and our team knows how to make "
            "little ones feel comfortable."
        ),
        "category": "services",
        "tags_json": ["pediatric", "children", "family"],
        "question_variants_json": [
            "Do you have a pediatric dentist?",
            "What age do you start seeing kids?",
            "Is this a family dental practice?",
            "Do you take toddlers?",
        ],
    },
    {
        "id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000008"),
        "tenant_id": _DEMO_TENANT_ID,
        "question": "What payment methods do you accept?",
        "answer": (
            "We accept cash, all major credit and debit cards (Visa, MasterCard, "
            "American Express, Discover), personal checks, and most dental insurance "
            "plans. We also offer CareCredit financing for larger procedures. "
            "Payment is due at the time of service unless prior arrangements have "
            "been made."
        ),
        "category": "billing",
        "tags_json": ["payment", "billing", "insurance"],
        "question_variants_json": [
            "Can I pay with a credit card?",
            "Do you take checks?",
            "Is CareCredit accepted?",
            "Do you offer payment plans?",
        ],
    },
    {
        "id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000009"),
        "tenant_id": _DEMO_TENANT_ID,
        "question": "Can I reschedule my appointment?",
        "answer": (
            "Yes, you can reschedule your appointment. We ask for at least 24 hours' "
            "notice when rescheduling so we can offer your slot to another patient. "
            "You can call us during business hours, use our patient portal, or if "
            "you are calling from the number we have on file, I can help reschedule "
            "you right now. Is there a specific day or time that works better for you?"
        ),
        "category": "scheduling",
        "tags_json": ["reschedule", "cancellation", "appointments"],
        "question_variants_json": [
            "I need to cancel my appointment",
            "Can I move my appointment to next week?",
            "Something came up, can I change my visit?",
            "What is your cancellation policy?",
        ],
    },
    {
        "id": UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000010"),
        "tenant_id": _DEMO_TENANT_ID,
        "question": "Where are you located?",
        "answer": (
            "We are located at 123 Maple Street, Suite 200, in Springfield, Illinois, "
            "zip code 62701. We are on the corner of Maple and 5th Street, in the "
            "Maplewood Professional Building. Free parking is available in the lot "
            "behind the building. We are also accessible by bus — the nearest stop "
            "is Maple & 5th on Route 12."
        ),
        "category": "location",
        "tags_json": ["location", "address", "directions", "parking"],
        "question_variants_json": [
            "What is your address?",
            "How do I get there?",
            "Is there parking?",
            "Where are you on Maple Street?",
        ],
    },
]


async def seed_faq_entries(db: AsyncSession, tenant_id: UUID) -> None:
    """Insert FAQ entries for the demo tenant."""
    for entry_data in FAQ_ENTRIES:
        result = await db.execute(select(FAQEntry.id).where(FAQEntry.id == entry_data["id"]))
        if result.scalar_one_or_none():
            continue
        entry = FAQEntry(**entry_data)
        entry.use_count = 0
        db.add(entry)
    await db.flush()
    logger.info("seed.faq_entries_done", count=len(FAQ_ENTRIES))


# ---------------------------------------------------------------------------
# 5. Routing Rules
# ---------------------------------------------------------------------------

ROUTING_RULES: List[Dict[str, Any]] = [
    {
        "id": _RULE_IDS[0],
        "tenant_id": _DEMO_TENANT_ID,
        "name": "After-Hours → AI Agent",
        "description": "When the office is closed, route all calls to the AI answering agent.",
        "priority": 10,
        "rule_type": RoutingType.TIME_BASED,
        "conditions_json": {
            "during_business_hours": False,
            "day_of_week": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
        },
        "action": RoutingAction.ANSWER,
        "action_config_json": {
            "agent_type": "ai_virtual_receptionist",
            "greeting": "after_hours",
            "offer_voicemail": True,
            "max_call_duration": 600,
        },
        "is_active": True,
        "match_count": 0,
    },
    {
        "id": _RULE_IDS[1],
        "tenant_id": _DEMO_TENANT_ID,
        "name": "Emergency Keyword → Transfer",
        "description": (
            "If the caller mentions emergency-related keywords, immediately transfer "
            "to the emergency line."
        ),
        "priority": 5,
        "rule_type": RoutingType.INTENT_BASED,
        "conditions_json": {
            "intents": ["emergency", "pain", "bleeding", "knocked_out", "severe"],
            "keywords": ["emergency", "pain", "bleeding", "knocked out", "severe", "urgent", "911"],
            "confidence_threshold": 0.6,
        },
        "action": RoutingAction.TRANSFER,
        "action_config_json": {
            "transfer_number": "+1-555-0199",
            "transfer_message": "Connecting you to our emergency line now.",
            "fallback_to_voicemail": True,
            "timeout_seconds": 30,
        },
        "is_active": True,
        "match_count": 0,
    },
    {
        "id": _RULE_IDS[2],
        "tenant_id": _DEMO_TENANT_ID,
        "name": "New Patient → Book Consultation",
        "description": (
            "When a caller identifies as a new patient, offer to book a "
            "complimentary consultation."
        ),
        "priority": 20,
        "rule_type": RoutingType.INTENT_BASED,
        "conditions_json": {
            "intents": ["new_patient", "consultation", "first_visit"],
            "keywords": ["new patient", "first time", "consultation", "new here", "never been"],
            "confidence_threshold": 0.5,
        },
        "action": RoutingAction.ANSWER,
        "action_config_json": {
            "agent_type": "ai_virtual_receptionist",
            "greeting": "new_patient_welcome",
            "offer_consultation": True,
            "consultation_type": "new_patient_exam",
        },
        "is_active": True,
        "match_count": 0,
    },
    {
        "id": _RULE_IDS[3],
        "tenant_id": _DEMO_TENANT_ID,
        "name": "Business Hours → AI Receptionist",
        "description": "During business hours, let the AI receptionist handle all calls.",
        "priority": 30,
        "rule_type": RoutingType.TIME_BASED,
        "conditions_json": {
            "during_business_hours": True,
        },
        "action": RoutingAction.ANSWER,
        "action_config_json": {
            "agent_type": "ai_virtual_receptionist",
            "greeting": "business_hours",
            "offer_transfer": True,
            "transfer_on_request": True,
        },
        "is_active": True,
        "match_count": 0,
    },
    {
        "id": _RULE_IDS[4],
        "tenant_id": _DEMO_TENANT_ID,
        "name": "Default Fallback",
        "description": "Catch-all rule to ensure every call is answered by the AI.",
        "priority": 999,
        "rule_type": RoutingType.DEFAULT,
        "conditions_json": {},
        "action": RoutingAction.ANSWER,
        "action_config_json": {
            "agent_type": "ai_virtual_receptionist",
            "greeting": "default",
        },
        "is_active": True,
        "match_count": 0,
    },
]


async def seed_routing_rules(db: AsyncSession, tenant_id: UUID) -> None:
    """Insert routing rules for the demo tenant."""
    for rule_data in ROUTING_RULES:
        result = await db.execute(select(RoutingRule.id).where(RoutingRule.id == rule_data["id"]))
        if result.scalar_one_or_none():
            continue
        rule = RoutingRule(**rule_data)
        db.add(rule)
    await db.flush()
    logger.info("seed.routing_rules_done", count=len(ROUTING_RULES))


# ---------------------------------------------------------------------------
# 6. Business Hours
# ---------------------------------------------------------------------------

BUSINESS_HOURS: List[Dict[str, Any]] = [
    {"day_of_week": "monday",    "open_time": time(9, 0),  "close_time": time(17, 0), "is_closed": False},
    {"day_of_week": "tuesday",   "open_time": time(9, 0),  "close_time": time(17, 0), "is_closed": False},
    {"day_of_week": "wednesday", "open_time": time(9, 0),  "close_time": time(17, 0), "is_closed": False},
    {"day_of_week": "thursday",  "open_time": time(9, 0),  "close_time": time(17, 0), "is_closed": False},
    {"day_of_week": "friday",    "open_time": time(9, 0),  "close_time": time(17, 0), "is_closed": False},
    {"day_of_week": "saturday",  "open_time": time(9, 0),  "close_time": time(13, 0), "is_closed": False},
    {"day_of_week": "sunday",    "open_time": time(0, 0),  "close_time": time(0, 0),  "is_closed": True},
]


async def seed_business_hours(db: AsyncSession, tenant_id: UUID) -> None:
    """Insert business hours for the demo tenant."""
    for i, bh_data in enumerate(BUSINESS_HOURS):
        bh_id = UUID(f"bbbbbbbb-bbbb-bbbb-bbbb-{i:012d}")
        result = await db.execute(select(BusinessHours.id).where(BusinessHours.id == bh_id))
        if result.scalar_one_or_none():
            continue
        bh = BusinessHours(
            id=bh_id,
            tenant_id=tenant_id,
            timezone="America/New_York",
            effective_from=date(2024, 1, 1),
            is_override=False,
            **bh_data,
        )
        db.add(bh)
    await db.flush()
    logger.info("seed.business_hours_done", count=len(BUSINESS_HOURS))


# ---------------------------------------------------------------------------
# 7. Holiday Schedule
# ---------------------------------------------------------------------------

HOLIDAYS: List[Dict[str, Any]] = [
    {"date": date(2024, 1, 1),  "name": "New Year's Day",          "is_closed": True,  "open_time": None,        "close_time": None},
    {"date": date(2024, 5, 27), "name": "Memorial Day",            "is_closed": True,  "open_time": None,        "close_time": None},
    {"date": date(2024, 7, 4),  "name": "Independence Day",        "is_closed": True,  "open_time": None,        "close_time": None},
    {"date": date(2024, 9, 2),  "name": "Labor Day",               "is_closed": True,  "open_time": None,        "close_time": None},
    {"date": date(2024, 11, 28),"name": "Thanksgiving Day",        "is_closed": True,  "open_time": None,        "close_time": None},
    {"date": date(2024, 11, 29),"name": "Day After Thanksgiving",  "is_closed": False, "open_time": time(9, 0),  "close_time": time(13, 0)},
    {"date": date(2024, 12, 24),"name": "Christmas Eve",           "is_closed": False, "open_time": time(9, 0),  "close_time": time(13, 0)},
    {"date": date(2024, 12, 25),"name": "Christmas Day",           "is_closed": True,  "open_time": None,        "close_time": None},
    {"date": date(2024, 12, 31),"name": "New Year's Eve",          "is_closed": False, "open_time": time(9, 0),  "close_time": time(14, 0)},
]


async def seed_holiday_schedule(db: AsyncSession, tenant_id: UUID) -> None:
    """Insert holiday schedule for the demo tenant."""
    for i, h_data in enumerate(HOLIDAYS):
        h_id = UUID(f"cccccccc-cccc-cccc-cccc-{i:012d}")
        result = await db.execute(select(HolidaySchedule.id).where(HolidaySchedule.id == h_id))
        if result.scalar_one_or_none():
            continue
        holiday = HolidaySchedule(
            id=h_id,
            tenant_id=tenant_id,
            timezone="America/New_York",
            is_recurring=True,
            **h_data,
        )
        db.add(holiday)
    await db.flush()
    logger.info("seed.holiday_schedule_done", count=len(HOLIDAYS))


# ---------------------------------------------------------------------------
# 8. AI Prompts
# ---------------------------------------------------------------------------

PROMPTS: List[Dict[str, Any]] = [
    {
        "id": _PROMPT_IDS[0],
        "tenant_id": _DEMO_TENANT_ID,
        "name": "System Prompt — Dental Receptionist",
        "description": "Core personality and behavior instructions for the AI agent.",
        "prompt_type": "system",
        "content": (
            "You are Alex, a warm and professional virtual receptionist at Smith Dental "
            "Clinic. Your personality is friendly, patient, and reassuring. You speak "
            "clearly and concisely.\n\n"
            "CORE RESPONSIBILITIES:\n"
            "1. Greet every caller warmly by name if available.\n"
            "2. Answer questions using the FAQ knowledge base.\n"
            "3. Help patients schedule, reschedule, or cancel appointments.\n"
            "4. Take detailed messages when the caller prefers or when staff is unavailable.\n"
            "5. Triage emergencies quickly and transfer to the emergency line when needed.\n\n"
            "TONE GUIDELINES:\n"
            "- Always be empathetic, especially for patients in pain.\n"
            "- Use the caller's name at least once during the conversation.\n"
            "- Confirm action items before ending the call.\n"
            "- Keep responses to 2-3 sentences unless detailed information is needed.\n\n"
            "ESCALATION:\n"
            "- If a caller asks for Dr. Smith specifically, offer to take a message or transfer.\n"
            "- If a caller is frustrated or the conversation exceeds 5 minutes, offer to transfer "
            "to a human staff member.\n"
            "- If you detect emergency keywords (severe pain, bleeding, knocked-out tooth), "
            "immediately offer to transfer to the emergency line."
        ),
        "variables_json": ["caller_name", "business_name", "current_time"],
        "version": 1,
        "is_active": True,
        "use_count": 0,
    },
    {
        "id": _PROMPT_IDS[1],
        "tenant_id": _DEMO_TENANT_ID,
        "name": "Greeting — Business Hours",
        "description": "First message the AI says when answering during business hours.",
        "prompt_type": "greeting",
        "content": (
            "Good {time_of_day}, thank you for calling Smith Dental Clinic. "
            "My name is Alex, your virtual receptionist. How may I assist you today?"
        ),
        "variables_json": ["time_of_day", "caller_name"],
        "version": 1,
        "is_active": True,
        "use_count": 0,
    },
    {
        "id": _PROMPT_IDS[2],
        "tenant_id": _DEMO_TENANT_ID,
        "name": "Greeting — After Hours",
        "description": "First message the AI says when answering after hours.",
        "prompt_type": "greeting",
        "content": (
            "Good {time_of_day}, you have reached Smith Dental Clinic. Our office is "
            "currently closed. I am Alex, the virtual receptionist, and I can still help "
            "you. For emergencies, I can transfer you to our 24/7 emergency line. "
            "Otherwise, how may I assist you?"
        ),
        "variables_json": ["time_of_day", "caller_name"],
        "version": 2,
        "is_active": True,
        "use_count": 0,
    },
    {
        "id": _PROMPT_IDS[3],
        "tenant_id": _DEMO_TENANT_ID,
        "name": "Hold Message",
        "description": "Played when the caller is placed on hold during a transfer.",
        "prompt_type": "transfer",
        "content": (
            "Thank you for holding. I am connecting you now. If the line is busy, "
            "I can take a detailed message and ensure someone follows up with you promptly."
        ),
        "variables_json": [],
        "version": 1,
        "is_active": True,
        "use_count": 0,
    },
    {
        "id": _PROMPT_IDS[4],
        "tenant_id": _DEMO_TENANT_ID,
        "name": "Goodbye Message",
        "description": "Closing message before ending a call.",
        "prompt_type": "closing",
        "content": (
            "Thank you for calling Smith Dental Clinic. We appreciate your trust in us. "
            "Have a wonderful day, and we look forward to seeing you soon!"
        ),
        "variables_json": [],
        "version": 1,
        "is_active": True,
        "use_count": 0,
    },
]


async def seed_prompts(db: AsyncSession, tenant_id: UUID) -> None:
    """Insert AI prompts for the demo tenant."""
    for prompt_data in PROMPTS:
        result = await db.execute(select(Prompt.id).where(Prompt.id == prompt_data["id"]))
        if result.scalar_one_or_none():
            continue
        prompt = Prompt(**prompt_data)
        db.add(prompt)
    await db.flush()
    logger.info("seed.prompts_done", count=len(PROMPTS))


# ---------------------------------------------------------------------------
# 9. Sample Call Records (10 calls)
# ---------------------------------------------------------------------------

_SAMPLE_CALLS: List[Dict[str, Any]] = [
    # ── 3 Appointment Bookings ──
    {
        "id": _CALL_IDS[0],
        "call_sid": f"demo-call-apt-001-{secrets.token_hex(4)}",
        "caller_number": "+1-555-0201",
        "caller_name": "John Williams",
        "destination_number": "+1-555-0100",
        "status": CallStatus.COMPLETED,
        "result": CallResult.SUCCESS,
        "direction": CallDirection.INBOUND,
        "started_at": datetime(2024, 6, 10, 10, 15, 0),
        "answered_at": datetime(2024, 6, 10, 10, 15, 2),
        "ended_at": datetime(2024, 6, 10, 10, 18, 30),
        "duration_seconds": 208,
        "talk_time_seconds": 206,
        "ai_handled": True,
        "ai_model_used": AIModel.LLAMA3_8B,
        "transcript_summary": (
            "Caller John Williams wanted to schedule a routine cleaning. "
            "AI offered available slots on Thursday and Friday. Caller chose "
            "Friday at 10 AM. Appointment confirmed."
        ),
        "sentiment_score": Decimal("0.72"),
        "intent_detected": "appointment",
        "llm_tokens_used": 312,
        "tts_chars_used": 485,
        "tags": ["appointment", "cleaning", "new_patient"],
        "metadata_json": {"resolution": "appointment_booked", "satisfaction": "high"},
    },
    {
        "id": _CALL_IDS[1],
        "call_sid": f"demo-call-apt-002-{secrets.token_hex(4)}",
        "caller_number": "+1-555-0202",
        "caller_name": "Maria Garcia",
        "destination_number": "+1-555-0100",
        "status": CallStatus.COMPLETED,
        "result": CallResult.SUCCESS,
        "direction": CallDirection.INBOUND,
        "started_at": datetime(2024, 6, 10, 14, 30, 0),
        "answered_at": datetime(2024, 6, 10, 14, 30, 1),
        "ended_at": datetime(2024, 6, 10, 14, 33, 45),
        "duration_seconds": 224,
        "talk_time_seconds": 223,
        "ai_handled": True,
        "ai_model_used": AIModel.LLAMA3_8B,
        "transcript_summary": (
            "Caller Maria Garcia called to book a teeth whitening consultation. "
            "AI explained the two options (in-office and take-home). Caller opted "
            "for in-office treatment and scheduled for next Tuesday at 2 PM."
        ),
        "sentiment_score": Decimal("0.85"),
        "intent_detected": "appointment",
        "llm_tokens_used": 398,
        "tts_chars_used": 620,
        "tags": ["appointment", "cosmetic", "whitening"],
        "metadata_json": {"resolution": "appointment_booked", "satisfaction": "high"},
    },
    {
        "id": _CALL_IDS[2],
        "call_sid": f"demo-call-apt-003-{secrets.token_hex(4)}",
        "caller_number": "+1-555-0203",
        "caller_name": "Robert Chen",
        "destination_number": "+1-555-0100",
        "status": CallStatus.COMPLETED,
        "result": CallResult.SUCCESS,
        "direction": CallDirection.INBOUND,
        "started_at": datetime(2024, 6, 11, 9, 5, 0),
        "answered_at": datetime(2024, 6, 11, 9, 5, 1),
        "ended_at": datetime(2024, 6, 11, 9, 7, 10),
        "duration_seconds": 129,
        "talk_time_seconds": 128,
        "ai_handled": True,
        "ai_model_used": AIModel.LLAMA3_8B,
        "transcript_summary": (
            "Caller Robert Chen needed to reschedule his Wednesday appointment. "
            "AI offered Thursday morning slots. Caller selected Thursday 11 AM. "
            "Old appointment cancelled, new one confirmed."
        ),
        "sentiment_score": Decimal("0.60"),
        "intent_detected": "reschedule",
        "llm_tokens_used": 245,
        "tts_chars_used": 380,
        "tags": ["appointment", "reschedule"],
        "metadata_json": {"resolution": "appointment_rescheduled", "satisfaction": "medium"},
    },
    # ── 4 Messages Taken ──
    {
        "id": _CALL_IDS[3],
        "call_sid": f"demo-call-msg-004-{secrets.token_hex(4)}",
        "caller_number": "+1-555-0204",
        "caller_name": "Patricia Moore",
        "destination_number": "+1-555-0100",
        "status": CallStatus.COMPLETED,
        "result": CallResult.SUCCESS,
        "direction": CallDirection.INBOUND,
        "started_at": datetime(2024, 6, 11, 16, 45, 0),
        "answered_at": datetime(2024, 6, 11, 16, 45, 1),
        "ended_at": datetime(2024, 6, 11, 16, 47, 20),
        "duration_seconds": 139,
        "talk_time_seconds": 138,
        "ai_handled": True,
        "ai_model_used": AIModel.LLAMA3_8B,
        "transcript_summary": (
            "Caller Patricia Moore wanted to speak with Dr. Smith about a billing "
            "question. AI explained Dr. Smith was with a patient and offered to take "
            "a message. Caller left her name, callback number, and a brief question "
            "about insurance coverage for a recent procedure."
        ),
        "sentiment_score": Decimal("0.45"),
        "intent_detected": "message",
        "llm_tokens_used": 278,
        "tts_chars_used": 420,
        "tags": ["message", "billing", "callback_requested"],
        "metadata_json": {"resolution": "message_taken", "satisfaction": "medium"},
    },
    {
        "id": _CALL_IDS[4],
        "call_sid": f"demo-call-msg-005-{secrets.token_hex(4)}",
        "caller_number": "+1-555-0205",
        "caller_name": "David Thompson",
        "destination_number": "+1-555-0100",
        "status": CallStatus.COMPLETED,
        "result": CallResult.SUCCESS,
        "direction": CallDirection.INBOUND,
        "started_at": datetime(2024, 6, 12, 11, 20, 0),
        "answered_at": datetime(2024, 6, 12, 11, 20, 2),
        "ended_at": datetime(2024, 6, 12, 11, 22, 0),
        "duration_seconds": 118,
        "talk_time_seconds": 116,
        "ai_handled": True,
        "ai_model_used": AIModel.LLAMA3_8B,
        "transcript_summary": (
            "Caller David Thompson requested a copy of his dental records. AI "
            "explained the records release process and took a message with his "
            "name, date of birth, and the address where records should be sent. "
            "Staff will process within 2 business days."
        ),
        "sentiment_score": Decimal("0.50"),
        "intent_detected": "records_request",
        "llm_tokens_used": 265,
        "tts_chars_used": 395,
        "tags": ["message", "records_request"],
        "metadata_json": {"resolution": "message_taken", "satisfaction": "medium"},
    },
    {
        "id": _CALL_IDS[5],
        "call_sid": f"demo-call-msg-006-{secrets.token_hex(4)}",
        "caller_number": "+1-555-0206",
        "caller_name": "Linda Foster",
        "destination_number": "+1-555-0100",
        "status": CallStatus.COMPLETED,
        "result": CallResult.SUCCESS,
        "direction": CallDirection.INBOUND,
        "started_at": datetime(2024, 6, 12, 15, 10, 0),
        "answered_at": datetime(2024, 6, 12, 15, 10, 1),
        "ended_at": datetime(2024, 6, 12, 15, 12, 30),
        "duration_seconds": 149,
        "talk_time_seconds": 148,
        "ai_handled": True,
        "ai_model_used": AIModel.LLAMA3_8B,
        "transcript_summary": (
            "Caller Linda Foster called about her son's upcoming appointment. "
            "She had questions about sedation options for children. AI took a "
            "detailed message about her concerns so the pediatric specialist "
            "can call her back with specific guidance."
        ),
        "sentiment_score": Decimal("0.30"),
        "intent_detected": "question",
        "llm_tokens_used": 290,
        "tts_chars_used": 440,
        "tags": ["message", "pediatric", "question"],
        "metadata_json": {"resolution": "message_taken", "satisfaction": "medium"},
    },
    {
        "id": _CALL_IDS[6],
        "call_sid": f"demo-call-msg-007-{secrets.token_hex(4)}",
        "caller_number": "+1-555-0207",
        "caller_name": "James Anderson",
        "destination_number": "+1-555-0100",
        "status": CallStatus.VOICEMAIL,
        "result": CallResult.VOICEMAIL_LEFT,
        "direction": CallDirection.INBOUND,
        "started_at": datetime(2024, 6, 13, 8, 30, 0),
        "answered_at": datetime(2024, 6, 13, 8, 30, 1),
        "ended_at": datetime(2024, 6, 13, 8, 35, 0),
        "duration_seconds": 300,
        "talk_time_seconds": 299,
        "ai_handled": True,
        "ai_model_used": AIModel.LLAMA3_8B,
        "transcript_summary": (
            "Caller James Anderson reached voicemail after hours. He left a message "
            "requesting a callback to discuss implant options. The AI transcription "
            "captured his contact details and primary concern accurately."
        ),
        "sentiment_score": Decimal("0.55"),
        "intent_detected": "voicemail",
        "voicemail_left": True,
        "voicemail_duration": 120,
        "llm_tokens_used": 180,
        "tts_chars_used": 200,
        "tags": ["voicemail", "after_hours", "implants"],
        "metadata_json": {"resolution": "voicemail_left", "satisfaction": "medium"},
    },
    # ── 2 FAQ Answered ──
    {
        "id": _CALL_IDS[7],
        "call_sid": f"demo-call-faq-008-{secrets.token_hex(4)}",
        "caller_number": "+1-555-0208",
        "caller_name": "Susan Lee",
        "destination_number": "+1-555-0100",
        "status": CallStatus.COMPLETED,
        "result": CallResult.SUCCESS,
        "direction": CallDirection.INBOUND,
        "started_at": datetime(2024, 6, 13, 13, 0, 0),
        "answered_at": datetime(2024, 6, 13, 13, 0, 1),
        "ended_at": datetime(2024, 6, 13, 13, 1, 15),
        "duration_seconds": 74,
        "talk_time_seconds": 73,
        "ai_handled": True,
        "ai_model_used": AIModel.LLAMA3_8B,
        "transcript_summary": (
            "Caller Susan Lee asked about office hours and insurance acceptance. "
            "AI answered both questions using FAQ data. Caller was satisfied and "
            "said she would schedule online. Call ended cordially."
        ),
        "sentiment_score": Decimal("0.90"),
        "intent_detected": "information",
        "llm_tokens_used": 155,
        "tts_chars_used": 240,
        "tags": ["faq", "hours", "insurance"],
        "metadata_json": {"resolution": "faq_answered", "satisfaction": "high"},
    },
    {
        "id": _CALL_IDS[8],
        "call_sid": f"demo-call-faq-009-{secrets.token_hex(4)}",
        "caller_number": "+1-555-0209",
        "caller_name": "Michael Brown",
        "destination_number": "+1-555-0100",
        "status": CallStatus.COMPLETED,
        "result": CallResult.SUCCESS,
        "direction": CallDirection.INBOUND,
        "started_at": datetime(2024, 6, 14, 10, 45, 0),
        "answered_at": datetime(2024, 6, 14, 10, 45, 1),
        "ended_at": datetime(2024, 6, 14, 10, 46, 30),
        "duration_seconds": 89,
        "talk_time_seconds": 88,
        "ai_handled": True,
        "ai_model_used": AIModel.LLAMA3_8B,
        "transcript_summary": (
            "Caller Michael Brown asked about payment methods and whether the office "
            "sees children. AI confirmed all major payment methods are accepted and "
            "that pediatric dentistry is available. Caller thanked the AI and ended the call."
        ),
        "sentiment_score": Decimal("0.80"),
        "intent_detected": "information",
        "llm_tokens_used": 168,
        "tts_chars_used": 260,
        "tags": ["faq", "payment", "pediatric"],
        "metadata_json": {"resolution": "faq_answered", "satisfaction": "high"},
    },
    # ── 1 Transferred ──
    {
        "id": _CALL_IDS[9],
        "call_sid": f"demo-call-trn-010-{secrets.token_hex(4)}",
        "caller_number": "+1-555-0210",
        "caller_name": "Emily Rodriguez",
        "destination_number": "+1-555-0100",
        "status": CallStatus.TRANSFERRED,
        "result": CallResult.TRANSFERRED,
        "direction": CallDirection.INBOUND,
        "started_at": datetime(2024, 6, 14, 16, 20, 0),
        "answered_at": datetime(2024, 6, 14, 16, 20, 1),
        "ended_at": datetime(2024, 6, 14, 16, 22, 0),
        "duration_seconds": 119,
        "talk_time_seconds": 118,
        "ai_handled": True,
        "ai_model_used": AIModel.LLAMA3_8B,
        "transcript_summary": (
            "Caller Emily Rodriguez reported severe tooth pain after a recent filling. "
            "AI triaged the situation, recognized it as a potential emergency, and "
            "offered to transfer. Caller accepted. AI transferred to emergency line "
            "+1-555-0199. Call lasted ~2 minutes including hold time."
        ),
        "sentiment_score": Decimal("-0.35"),
        "intent_detected": "emergency",
        "transferred_to": "+1-555-0199",
        "transfer_reason": "Severe post-procedure pain — potential emergency",
        "llm_tokens_used": 210,
        "tts_chars_used": 310,
        "tags": ["emergency", "transferred", "pain", "post_procedure"],
        "metadata_json": {"resolution": "transferred", "satisfaction": "medium"},
    },
]


async def seed_sample_calls(db: AsyncSession, tenant_id: UUID) -> None:
    """Insert sample call records for the demo tenant."""
    for call_data in _SAMPLE_CALLS:
        result = await db.execute(select(Call.id).where(Call.id == call_data["id"]))
        if result.scalar_one_or_none():
            continue

        # Compute caller_id_hash
        call_data["caller_id_hash"] = _sha256_phone(call_data["caller_number"])
        call_data["estimated_cost"] = Decimal(str(
            round(call_data["duration_seconds"] * 0.008, 6)
        ))
        call_data["partition_key"] = call_data["started_at"].strftime("%Y-%m")
        call_data["tenant_id"] = tenant_id

        call = Call(**call_data)
        db.add(call)

        # Add a CallLeg for the caller
        leg = CallLeg(
            tenant_id=tenant_id,
            call_id=call_data["id"],
            leg_type="caller",
            leg_index=1,
            display_name=call_data.get("caller_name", "Unknown Caller"),
            phone_number=call_data["caller_number"],
            joined_at=call_data["started_at"],
            left_at=call_data["ended_at"],
            duration_seconds=call_data["duration_seconds"],
            status="disconnected",
        )
        db.add(leg)

    await db.flush()
    logger.info("seed.sample_calls_done", count=len(_SAMPLE_CALLS))


# ---------------------------------------------------------------------------
# 10. Sample Appointments
# ---------------------------------------------------------------------------

_SAMPLE_APPOINTMENTS: List[Dict[str, Any]] = [
    {
        "id": _APT_IDS[0],
        "call_id": _CALL_IDS[0],
        "caller_number": "+1-555-0201",
        "caller_name": "John Williams",
        "title": "Routine Cleaning",
        "description": "Six-month routine dental cleaning and exam.",
        "status": AppointmentStatus.CONFIRMED,
        "scheduled_date": date(2024, 6, 14),
        "start_time": time(10, 0),
        "end_time": time(10, 45),
        "timezone": "America/New_York",
        "appointment_type": "in_person",
        "location": "Smith Dental Clinic, Suite 200",
        "confirmed_at": datetime(2024, 6, 10, 10, 18, 30),
        "confirmed_by": "ai",
        "sync_status": "pending",
    },
    {
        "id": _APT_IDS[1],
        "call_id": _CALL_IDS[1],
        "caller_number": "+1-555-0202",
        "caller_name": "Maria Garcia",
        "title": "Teeth Whitening Consultation",
        "description": "In-office teeth whitening consultation. Discuss options and pricing.",
        "status": AppointmentStatus.CONFIRMED,
        "scheduled_date": date(2024, 6, 18),
        "start_time": time(14, 0),
        "end_time": time(14, 30),
        "timezone": "America/New_York",
        "appointment_type": "in_person",
        "location": "Smith Dental Clinic, Suite 200",
        "confirmed_at": datetime(2024, 6, 10, 14, 33, 45),
        "confirmed_by": "ai",
        "sync_status": "pending",
    },
    {
        "id": _APT_IDS[2],
        "call_id": _CALL_IDS[2],
        "caller_number": "+1-555-0203",
        "caller_name": "Robert Chen",
        "title": "Rescheduled Check-Up",
        "description": "Rescheduled from June 12 to June 13 — general check-up.",
        "status": AppointmentStatus.CONFIRMED,
        "scheduled_date": date(2024, 6, 13),
        "start_time": time(11, 0),
        "end_time": time(11, 30),
        "timezone": "America/New_York",
        "appointment_type": "in_person",
        "location": "Smith Dental Clinic, Suite 200",
        "confirmed_at": datetime(2024, 6, 11, 9, 7, 10),
        "confirmed_by": "ai",
        "sync_status": "pending",
    },
    {
        "id": _APT_IDS[3],
        "call_id": None,
        "caller_number": "+1-555-0211",
        "caller_name": "Karen Martinez",
        "title": "New Patient Exam",
        "description": "First visit — comprehensive exam, X-rays, and treatment plan discussion.",
        "status": AppointmentStatus.PENDING,
        "scheduled_date": date(2024, 6, 17),
        "start_time": time(9, 0),
        "end_time": time(10, 0),
        "timezone": "America/New_York",
        "appointment_type": "in_person",
        "location": "Smith Dental Clinic, Suite 200",
        "sync_status": "pending",
    },
    {
        "id": _APT_IDS[4],
        "call_id": None,
        "caller_number": "+1-555-0212",
        "caller_name": "Thomas Wright",
        "title": "Cavity Filling",
        "description": "Filling for lower left molar (tooth #19).",
        "status": AppointmentStatus.CONFIRMED,
        "scheduled_date": date(2024, 6, 19),
        "start_time": time(15, 0),
        "end_time": time(15, 45),
        "timezone": "America/New_York",
        "appointment_type": "in_person",
        "location": "Smith Dental Clinic, Suite 200",
        "confirmed_at": datetime(2024, 6, 10, 11, 0, 0),
        "confirmed_by": "staff",
        "sync_status": "synced",
        "external_id": "google-event-abc123",
        "external_provider": "google_calendar",
    },
]


async def seed_sample_appointments(db: AsyncSession, tenant_id: UUID) -> None:
    """Insert sample appointments for the demo tenant."""
    for apt_data in _SAMPLE_APPOINTMENTS:
        result = await db.execute(select(Appointment.id).where(Appointment.id == apt_data["id"]))
        if result.scalar_one_or_none():
            continue
        apt_data["tenant_id"] = tenant_id
        apt = Appointment(**apt_data)
        db.add(apt)
    await db.flush()
    logger.info("seed.sample_appointments_done", count=len(_SAMPLE_APPOINTMENTS))


# ---------------------------------------------------------------------------
# 11. Sample Messages (voicemail / callback requests)
# ---------------------------------------------------------------------------

async def seed_sample_messages(db: AsyncSession, tenant_id: UUID) -> None:
    """Insert sample conversation messages for a few calls."""
    # Only seed for the first call (appointment booking) as a detailed example
    call_id = _CALL_IDS[0]

    # Check if conversation already exists
    result = await db.execute(
        select(Conversation.id).where(Conversation.call_id == call_id)
    )
    if result.scalar_one_or_none():
        logger.debug("seed.conversation_exists", call_id=str(call_id))
        return

    conv_id = UUID("dddddddd-dddd-dddd-dddd-000000000001")
    conversation = Conversation(
        id=conv_id,
        tenant_id=tenant_id,
        call_id=call_id,
        turn_count=4,
        topic_category="appointment_booking",
        summary="Caller wanted a cleaning. AI offered slots, caller chose Friday 10 AM.",
        satisfaction_score=Decimal("0.72"),
        resolved=True,
        resolution_type="appointment_booked",
        follow_up_required=False,
    )
    db.add(conversation)
    await db.flush()

    messages = [
        Message(
            id=UUID("eeeeeeee-eeee-eeee-eeee-000000000001"),
            tenant_id=tenant_id,
            conversation_id=conv_id,
            call_id=call_id,
            role="assistant",
            message_type="text",
            content=(
                "Good morning, thank you for calling Smith Dental Clinic. "
                "My name is Alex, your virtual receptionist. How may I assist you today?"
            ),
            sequence_number=1,
            llm_model=AIModel.LLAMA3_8B,
            tokens_completion=42,
        ),
        Message(
            id=UUID("eeeeeeee-eeee-eeee-eeee-000000000002"),
            tenant_id=tenant_id,
            conversation_id=conv_id,
            call_id=call_id,
            role="user",
            message_type="text",
            content="Hi Alex, I'd like to schedule a routine cleaning. Do you have anything this week?",
            sequence_number=2,
        ),
        Message(
            id=UUID("eeeeeeee-eeee-eeee-eeee-000000000003"),
            tenant_id=tenant_id,
            conversation_id=conv_id,
            call_id=call_id,
            role="assistant",
            message_type="text",
            content=(
                "Absolutely, John! I'd be happy to help you schedule a cleaning. "
                "I have availability on Thursday at 9 AM or Friday at 10 AM. "
                "Which would work better for you?"
            ),
            sequence_number=3,
            llm_model=AIModel.LLAMA3_8B,
            tokens_completion=38,
        ),
        Message(
            id=UUID("eeeeeeee-eeee-eeee-eeee-000000000004"),
            tenant_id=tenant_id,
            conversation_id=conv_id,
            call_id=call_id,
            role="user",
            message_type="text",
            content="Friday at 10 sounds great. Thank you!",
            sequence_number=4,
        ),
        Message(
            id=UUID("eeeeeeee-eeee-eeee-eeee-000000000005"),
            tenant_id=tenant_id,
            conversation_id=conv_id,
            call_id=call_id,
            role="assistant",
            message_type="text",
            content=(
                "Perfect! I've scheduled your routine cleaning for Friday, June 14th at "
                "10:00 AM. Please arrive 10 minutes early to complete any paperwork. "
                "We look forward to seeing you, John. Have a wonderful day!"
            ),
            sequence_number=5,
            llm_model=AIModel.LLAMA3_8B,
            tokens_completion=52,
        ),
    ]

    for msg in messages:
        db.add(msg)

    await db.flush()
    logger.info("seed.sample_messages_done", count=len(messages))


# ---------------------------------------------------------------------------
# 12. Audit log entry for seeding
# ---------------------------------------------------------------------------

async def seed_audit_entry(db: AsyncSession, tenant_id: UUID) -> None:
    """Write an audit log entry documenting the seed operation."""
    audit = AuditLog(
        tenant_id=tenant_id,
        actor_type="system",
        action="seed.demo_data",
        resource_type="tenant",
        resource_id=tenant_id,
        details_json={"seed_type": "demo", "version": "1.0.0"},
        severity="info",
    )
    db.add(audit)
    await db.flush()
    logger.info("seed.audit_entry_written")


# ---------------------------------------------------------------------------
# Master orchestrator
# ---------------------------------------------------------------------------

async def seed_all_demo_data(db: AsyncSession) -> Dict[str, Any]:
    """Run the complete demo data seeding pipeline.

    Returns:
        Summary dict with tenant_id, items seeded, and any notes.
    """
    logger.info("seed.pipeline_start")

    # 1. Plans (global)
    await seed_plan_definitions(db)

    # 2. Demo tenant
    tenant_id = await seed_demo_tenant(db)

    # 3. Demo user
    await seed_demo_user(db, tenant_id)

    # 4. FAQ entries
    await seed_faq_entries(db, tenant_id)

    # 5. Routing rules
    await seed_routing_rules(db, tenant_id)

    # 6. Business hours
    await seed_business_hours(db, tenant_id)

    # 7. Holiday schedule
    await seed_holiday_schedule(db, tenant_id)

    # 8. AI prompts
    await seed_prompts(db, tenant_id)

    # 9. Sample calls (with call legs)
    await seed_sample_calls(db, tenant_id)

    # 10. Sample appointments
    await seed_sample_appointments(db, tenant_id)

    # 11. Sample messages / conversations
    await seed_sample_messages(db, tenant_id)

    # 12. Audit entry
    await seed_audit_entry(db, tenant_id)

    summary = {
        "tenant_id": str(tenant_id),
        "tenant_slug": "smith-dental",
        "plans_seeded": 3,
        "faq_entries": 10,
        "routing_rules": 5,
        "business_hours": 7,
        "holidays": 9,
        "prompts": 5,
        "calls": 10,
        "appointments": 5,
        "messages": 5,
    }
    logger.info("seed.pipeline_complete", **summary)
    return summary


# ---------------------------------------------------------------------------
# Reset helpers
# ---------------------------------------------------------------------------

async def reset_all_data(db: AsyncSession) -> None:
    """Truncate all tenant-scoped data for a clean slate.

    **DANGER** — This deletes the demo tenant and everything linked to it.
    Plan definitions are preserved because they are global.
    """
    logger.warning("seed.reset_start")

    # Delete in dependency order (child tables first)
    from backend.db.models import (
        CallSummary,
        ToolCall,
        Message,
        Conversation,
        Transcript,
        CallLeg,
        Recording,
    )

    tables_to_truncate = [
        ("messages", Message),
        ("conversations", Conversation),
        ("tool_calls", ToolCall),
        ("transcripts", Transcript),
        ("call_legs", CallLeg),
        ("recordings", Recording),
        ("call_summaries", CallSummary),
        ("appointments", Appointment),
        ("calls", Call),
        ("prompts", Prompt),
        ("routing_rules", RoutingRule),
        ("holiday_schedules", HolidaySchedule),
        ("business_hours", BusinessHours),
        ("faq_entries", FAQEntry),
        ("caller_profiles", CallerProfile),
        ("notification_logs", NotificationLog),
        ("usage_records", UsageRecord),
        ("audit_logs", AuditLog),
        ("users", User),
        ("tenant_configs", TenantConfig),
        ("tenants", Tenant),
    ]

    for table_name, model_cls in tables_to_truncate:
        result = await db.execute(select(model_cls))
        count = len(result.scalars().all())
        await db.execute(model_cls.__table__.delete())
        logger.info("seed.reset_table", table=table_name, rows_deleted=count)

    logger.warning("seed.reset_complete")
