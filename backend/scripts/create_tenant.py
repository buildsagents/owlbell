"""
Owlbell — Interactive Tenant Onboarding Tool.

Location: backend/scripts/create_tenant.py

Guides a new business through setup, validates input, creates the tenant
record with sensible defaults, generates AI prompt suggestions, and prints
a configuration summary.

Usage::

    # Interactive mode (prompts for all fields)
    python -m backend.scripts.create_tenant

    # Quick mode with flags
    python -m backend.scripts.create_tenant \
        --name "Acme Legal" \
        --slug acme-legal \
        --phone "+1-555-0300" \
        --email "reception@acmelegal.example.com" \
        --timezone "America/Chicago" \
        --industry legal \
        --plan starter

    # With owner user
    python -m backend.scripts.create_tenant \
        --name "Acme Legal" \
        --owner-email "admin@acmelegal.example.com" \
        --owner-name "Jane Doe"

    # Dry-run (validate only, no DB write)
    python -m backend.scripts.create_tenant --dry-run --name "Test Co" --slug test-co

    # List existing tenants
    python -m backend.scripts.create_tenant --list

Exit codes::

    0  Success
    1  Validation error
    2  Database error
    3  Cancelled by user
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import secrets
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure project root is importable
sys.path.insert(0, str(__file__).rpartition("/backend/scripts")[0])

from backend.config import get_settings
from backend.db.models import (
    Tenant,
    TenantConfig,
    User,
    BusinessHours,
    FAQEntry,
    RoutingRule,
    Prompt,
)
from backend.db.models.enums import (
    AIModel,
    PlanTier,
    RoutingAction,
    RoutingType,
    TenantStatus,
    TranscriptSource,
    UserRole,
    VoiceType,
)
from backend.db.prompt_templates import TEMPLATES as SUGGESTED_PROMPT_TEMPLATES
from backend.db.seed_data import seed_plan_definitions

logger = logging.getLogger("create_tenant")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_INDUSTRIES = [
    "healthcare", "legal", "dental", "medical", "accounting",
    "real_estate", "retail", "restaurant", "salon", "fitness",
    "automotive", "technology", "consulting", "education",
    "insurance", "hvac", "plumbing", "electrical", "roofing",
    "pest_control", "property_management", "home_services",
    "other",
]

VALID_PLANS = ["free", "starter", "professional", "enterprise", "basic", "pro", "pro_plus"]

VALID_TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Phoenix",
    "America/Anchorage",
    "America/Honolulu",
    "Europe/London",
    "Europe/Paris",
    "Australia/Sydney",
    "Asia/Tokyo",
]

DEFAULT_ROUTING_RULES = [
    {
        "name": "Business Hours → AI Receptionist",
        "priority": 10,
        "rule_type": RoutingType.TIME_BASED,
        "conditions_json": {"during_business_hours": True},
        "action": RoutingAction.ANSWER,
        "action_config_json": {"agent_type": "ai_virtual_receptionist"},
    },
    {
        "name": "After Hours → Voicemail",
        "priority": 20,
        "rule_type": RoutingType.TIME_BASED,
        "conditions_json": {"during_business_hours": False},
        "action": RoutingAction.VOICEMAIL,
        "action_config_json": {
            "greeting": (
                "Thank you for calling {business_name}. Our office is currently "
                "closed. Please leave your name, phone number, and a brief message "
                "and we will return your call on the next business day. If you have "
                "an urgent emergency, please hang up and call our emergency line."
            ),
            "transcription_enabled": True,
            "callback_priority": "next_day",
        },
    },
    {
        "name": "Emergency Call Routing",
        "priority": 5,
        "rule_type": RoutingType.KEYWORD_BASED,
        "conditions_json": {
            "keywords": ["emergency", "urgent", "burst pipe", "no heat", "no ac",
                         "flood", "gas leak", "power out", "fire", "smoke"]
        },
        "action": RoutingAction.FORWARD,
        "action_config_json": {
            "forward_to": "emergency_line",
            "play_announcement": True,
            "announcement_text": "You are being connected to our emergency dispatch team. Please stay on the line.",
        },
    },
    {
        "name": "Default Fallback",
        "priority": 999,
        "rule_type": RoutingType.DEFAULT,
        "conditions_json": {},
        "action": RoutingAction.ANSWER,
        "action_config_json": {"agent_type": "ai_virtual_receptionist"},
    },
]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def validate_slug(value: str) -> str:
    """Validate tenant slug format."""
    if not re.match(r"^[a-z0-9-]+$", value):
        raise ValueError(
            f"Slug must contain only lowercase letters, numbers, and hyphens. "
            f"Got: '{value}'"
        )
    if len(value) < 3 or len(value) > 63:
        raise ValueError(f"Slug must be 3-63 characters. Got: {len(value)}")
    if value.startswith("-") or value.endswith("-"):
        raise ValueError("Slug cannot start or end with a hyphen.")
    return value


def validate_phone(value: str) -> str:
    """Validate E.164 phone number format."""
    # Accept formats: +1-555-0100, +15550100, (555) 010-1000
    cleaned = re.sub(r"[\s().-]", "", value)
    if not re.match(r"^\+\d{10,15}$", cleaned):
        raise ValueError(
            f"Phone must be E.164 format (e.g., +1-555-0100). Got: '{value}'"
        )
    return cleaned


def validate_email(value: str) -> str:
    """Basic email validation."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, value):
        raise ValueError(f"Invalid email address: '{value}'")
    return value.lower()


def validate_industry(value: str) -> str:
    """Validate industry against known list."""
    normalized = value.lower().replace(" ", "_").replace("-", "_")
    if normalized not in VALID_INDUSTRIES:
        raise ValueError(
            f"Unknown industry: '{value}'. Choose from: {', '.join(VALID_INDUSTRIES)}"
        )
    return normalized


def validate_timezone(value: str) -> str:
    """Validate timezone."""
    if value not in VALID_TIMEZONES:
        # Accept but warn
        logging.warning(f"Uncommon timezone: '{value}'. Using as-is.")
    return value


def validate_plan(value: str) -> PlanTier:
    """Validate plan tier."""
    mapping = {
        "free": PlanTier.FREE,
        "starter": PlanTier.STARTER,
        "basic": PlanTier.STARTER,
        "professional": PlanTier.PROFESSIONAL,
        "pro": PlanTier.PROFESSIONAL,
        "pro_plus": PlanTier.PROFESSIONAL,
        "enterprise": PlanTier.ENTERPRISE,
    }
    tier = mapping.get(value.lower())
    if tier is None:
        raise ValueError(
            f"Invalid plan: '{value}'. Choose from: {', '.join(VALID_PLANS)}"
        )
    return tier


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------


def prompt(text: str, default: Optional[str] = None, validator=None) -> str:
    """Prompt for input with optional default and validation."""
    while True:
        if default:
            user_input = input(f"{text} [{default}]: ").strip()
            if not user_input:
                user_input = default
        else:
            user_input = input(f"{text}: ").strip()

        if not user_input:
            print("  This field is required.")
            continue

        if validator:
            try:
                return validator(user_input)
            except ValueError as exc:
                print(f"  Error: {exc}")
                continue
        return user_input


def prompt_bool(text: str, default: bool = True) -> bool:
    """Prompt for a yes/no answer."""
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        user_input = input(f"{text}{suffix}: ").strip().lower()
        if not user_input:
            return default
        if user_input in ("y", "yes"):
            return True
        if user_input in ("n", "no"):
            return False
        print("  Please enter 'y' or 'n'.")


def prompt_choice(text: str, choices: List[str], default: Optional[str] = None) -> str:
    """Prompt user to select from a list."""
    print(f"\n{text}")
    for i, choice in enumerate(choices, 1):
        marker = " (default)" if choice == default else ""
        print(f"  {i}. {choice}{marker}")
    while True:
        user_input = input("  Select: ").strip()
        if not user_input and default:
            return default
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        if user_input in choices:
            return user_input
        print("  Invalid selection.")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


async def _db_session():
    """Create an async database session."""
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return session_maker(), engine


async def check_slug_available(db: AsyncSession, slug: str) -> bool:
    """Return True if the slug is not taken."""
    result = await db.execute(select(Tenant.id).where(Tenant.slug == slug))
    return result.scalar_one_or_none() is None


async def list_existing_tenants(db: AsyncSession) -> List[Dict[str, Any]]:
    """Return a list of existing tenants."""
    result = await db.execute(
        select(Tenant.id, Tenant.slug, Tenant.name, Tenant.plan_tier, Tenant.status)
        .order_by(Tenant.created_at.desc())
        .limit(50)
    )
    rows = result.all()
    return [
        {
            "id": str(r.id),
            "slug": r.slug,
            "name": r.name,
            "plan": r.plan_tier.value if r.plan_tier else "unknown",
            "status": r.status.value if r.status else "unknown",
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Tenant creation
# ---------------------------------------------------------------------------


async def create_tenant(
    db: AsyncSession,
    name: str,
    slug: str,
    phone: str,
    email: str,
    timezone: str,
    industry: str,
    plan_tier: PlanTier,
    address: Optional[str] = None,
    website: Optional[str] = None,
    owner_email: Optional[str] = None,
    owner_name: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Create a new tenant with all default configuration."""

    # -- Check slug availability ---------------------------------------------
    slug_available = await check_slug_available(db, slug)
    if not slug_available:
        raise ValueError(f"Tenant slug '{slug}' is already taken.")

    # -- Generate AI prompt suggestions ---------------------------------------
    industry_key = industry if industry in SUGGESTED_PROMPT_TEMPLATES else "default"
    prompt_suggestions = SUGGESTED_PROMPT_TEMPLATES[industry_key]
    system_prompt = prompt_suggestions["system"].format(business_name=name)
    greeting = prompt_suggestions["greeting"].format(business_name=name)

    tenant_id = uuid4()

    # -- Build tenant record --------------------------------------------------
    tenant = Tenant(
        id=tenant_id,
        slug=slug,
        name=name,
        status=TenantStatus.ACTIVE,
        plan_tier=plan_tier,
        business_name=name,
        business_phone=phone,
        business_email=email,
        business_timezone=timezone,
        business_address=address,
        business_website=website,
        industry=industry,
        ai_model=AIModel.LLAMA3_8B,
        ai_temperature=0.7,
        ai_max_tokens=256,
        ai_system_prompt=system_prompt,
        voice_type=VoiceType.PIPER_FEMALE_1,
        voice_speed=1.0,
        stt_model=TranscriptSource.WHISPER_LOCAL,
        stt_language="en",
        max_call_duration=600,
        voicemail_enabled=True,
        after_hours_action="voicemail",
        concurrent_calls_max=3,
        greeting_message=greeting,
        config_json={
            "timezone": timezone,
            "language": "en",
            "call_recording_enabled": True,
            "recording_disclosure_enabled": True,
            "recording_retention_days": 90,
        },
        features_json={
            "appointment_booking": True,
            "new_patient_intake": True,
        },
    )

    # -- Build tenant config --------------------------------------------------
    config = TenantConfig(
        tenant_id=tenant_id,
        ai_settings={
            "voice_id": "piper_female_1",
            "speech_rate": 1.0,
            "greeting": greeting,
            "language": "en",
            "timeout_handling": "offer_voicemail",
        },
        routing_rules={
            "after_hours_action": "voicemail",
            "overflow_action": "ai_agent",
        },
        notification_settings={
            "email_summary": True,
            "email_recipient": email,
            "missed_call_alert": True,
        },
        integrations={},
    )

    # -- Create owner user if provided ----------------------------------------
    owner_password_plain = None
    owner = None
    if owner_email and owner_name:
        # Generate a secure temporary password
        owner_password_plain = secrets.token_urlsafe(12)
        # bcrypt hash (we use a pre-computed pattern for demo; in production use bcrypt)
        # NOTE: In production, use passlib or bcrypt directly
        owner_id = uuid4()
        owner = User(
            id=owner_id,
            tenant_id=tenant_id,
            email=owner_email,
            # This is a placeholder — real onboarding would send a magic link
            password_hash="$2b$12$" + "x" * 53,  # Placeholder — set via magic link
            first_name=owner_name.split()[0],
            last_name=" ".join(owner_name.split()[1:]) if len(owner_name.split()) > 1 else "",
            role=UserRole.ADMIN,
            is_active=True,
            timezone=timezone,
        )

    if dry_run:
        return {
            "dry_run": True,
            "tenant_id": str(tenant_id),
            "slug": slug,
            "name": name,
            "plan": plan_tier.value,
            "system_prompt_preview": system_prompt[:120] + "...",
            "greeting_preview": greeting[:120] + "...",
            "owner": {
                "email": owner_email,
                "name": owner_name,
                "temp_password": owner_password_plain,
            } if owner else None,
        }

    # -- Persist to database --------------------------------------------------
    db.add(tenant)
    db.add(config)
    if owner:
        db.add(owner)
    await db.flush()

    # -- Create default routing rules -----------------------------------------
    for i, rule_data in enumerate(DEFAULT_ROUTING_RULES):
        rule = RoutingRule(
            id=uuid4(),
            tenant_id=tenant_id,
            name=rule_data["name"],
            priority=rule_data["priority"],
            rule_type=rule_data["rule_type"],
            conditions_json=rule_data["conditions_json"],
            action=rule_data["action"],
            action_config_json=rule_data["action_config_json"],
            is_active=True,
            match_count=0,
        )
        db.add(rule)

    # -- Create default business hours (Mon-Fri 9-5) -------------------------
    from datetime import time
    days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    for day in days:
        bh = BusinessHours(
            id=uuid4(),
            tenant_id=tenant_id,
            day_of_week=day,
            open_time=time(9, 0),
            close_time=time(17, 0),
            is_closed=False,
            timezone=timezone,
            is_override=False,
        )
        db.add(bh)
    # Weekend closed
    for day in ["saturday", "sunday"]:
        bh = BusinessHours(
            id=uuid4(),
            tenant_id=tenant_id,
            day_of_week=day,
            open_time=time(0, 0),
            close_time=time(0, 0),
            is_closed=True,
            timezone=timezone,
            is_override=False,
        )
        db.add(bh)

    # -- Create default prompts -----------------------------------------------
    for prompt_type, content in prompt_suggestions.items():
        formatted_content = content.format(business_name=name)
        prompt = Prompt(
            id=uuid4(),
            tenant_id=tenant_id,
            name=f"Default {prompt_type.capitalize()}",
            prompt_type=prompt_type,
            content=formatted_content,
            variables_json=["business_name"],
            version=1,
            is_active=True,
            use_count=0,
        )
        db.add(prompt)

    await db.flush()

    return {
        "tenant_id": str(tenant_id),
        "slug": slug,
        "name": name,
        "plan": plan_tier.value,
        "phone": phone,
        "email": email,
        "timezone": timezone,
        "industry": industry,
        "system_prompt_preview": system_prompt[:120] + "...",
        "greeting_preview": greeting[:120] + "...",
        "owner": {
            "email": owner_email,
            "name": owner_name,
            "temp_password": owner_password_plain,
            "note": "Send magic link or temp password via secure channel",
        } if owner else None,
        "routing_rules_created": len(DEFAULT_ROUTING_RULES),
        "business_days_set": len(days),
    }


# ---------------------------------------------------------------------------
# Print configuration summary
# ---------------------------------------------------------------------------


def print_summary(result: Dict[str, Any]) -> None:
    """Print a beautiful configuration summary."""
    print("\n" + "=" * 60)
    if result.get("dry_run"):
        print("DRY RUN — No database changes made")
        print("=" * 60)
    else:
        print("TENANT CREATED SUCCESSFULLY")
        print("=" * 60)

    print(f"\n  Business Name:    {result['name']}")
    print(f"  Slug:             {result['slug']}")
    print(f"  Tenant ID:        {result['tenant_id']}")
    print(f"  Plan Tier:        {result['plan']}")
    if not result.get("dry_run"):
        print(f"  Phone:            {result['phone']}")
        print(f"  Email:            {result['email']}")
        print(f"  Timezone:         {result['timezone']}")
        print(f"  Industry:         {result['industry']}")

    print(f"\n  --- AI Configuration ---")
    print(f"  System Prompt:    {result['system_prompt_preview']}")
    print(f"  Greeting:         {result['greeting_preview']}")

    if result.get("owner"):
        print(f"\n  --- Owner Account ---")
        print(f"  Name:             {result['owner']['name']}")
        print(f"  Email:            {result['owner']['email']}")
        if result["owner"].get("temp_password"):
            print(f"  Temp Password:    {result['owner']['temp_password']}")
        if result["owner"].get("note"):
            print(f"  Note:             {result['owner']['note']}")

    if not result.get("dry_run"):
        print(f"\n  --- Defaults Created ---")
        print(f"  Routing Rules:    {result['routing_rules_created']}")
        print(f"  Business Days:    Mon-Fri 9:00 AM - 5:00 PM")
        print(f"  AI Prompts:       system + greeting")

    print("\n" + "=" * 60)
    print("Next steps:")
    print("  1. Log into the dashboard: http://localhost:5173")
    print(f"  2. Configure phone number routing for: {result.get('phone', 'N/A')}")
    print("  3. Customize AI prompts in Settings > AI Configuration")
    print("  4. Add FAQ entries in Knowledge Base")
    print("  5. Test with a simulated call")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------


async def interactive_mode(db: AsyncSession, dry_run: bool = False) -> Dict[str, Any]:
    """Run the full interactive tenant creation wizard."""
    print("\n" + "=" * 60)
    print("  Owlbell — New Tenant Onboarding")
    print("=" * 60)
    print("\nLet's set up your new business on Owlbell.\n")

    # -- Business info --------------------------------------------------------
    print("--- Business Information ---")
    name = prompt("Business name")

    # Auto-suggest slug
    suggested_slug = name.lower().replace(" ", "-").replace("&", "and")
    suggested_slug = re.sub(r"[^a-z0-9-]", "", suggested_slug)
    suggested_slug = re.sub(r"-+", "-", suggested_slug).strip("-")[:63]

    slug = prompt("URL slug (used in URLs)", default=suggested_slug, validator=validate_slug)

    # Check availability
    available = await check_slug_available(db, slug)
    if not available:
        print(f"  ERROR: Slug '{slug}' is already taken.")
        while not available:
            slug = prompt("Choose a different slug", validator=validate_slug)
            available = await check_slug_available(db, slug)

    phone = prompt("Business phone (E.164, e.g. +1-555-0100)", validator=validate_phone)
    email = prompt("Business email", validator=validate_email)
    timezone = prompt_choice("Timezone", VALID_TIMEZONES, default="America/New_York")
    industry = prompt_choice("Industry", VALID_INDUSTRIES, default="other")
    plan = prompt_choice("Plan tier", VALID_PLANS, default="starter")
    address = prompt("Business address (optional)", default="") or None
    website = prompt("Website URL (optional)", default="") or None

    # -- Owner info -----------------------------------------------------------
    print("\n--- Owner Account ---")
    create_owner = prompt_bool("Create an owner account?", default=True)
    owner_email = None
    owner_name = None
    if create_owner:
        owner_email = prompt("Owner email", default=email, validator=validate_email)
        owner_name = prompt("Owner full name")

    # -- Confirm --------------------------------------------------------------
    print("\n--- Summary ---")
    print(f"  Business:   {name}")
    print(f"  Slug:       {slug}")
    print(f"  Phone:      {phone}")
    print(f"  Email:      {email}")
    print(f"  Timezone:   {timezone}")
    print(f"  Industry:   {industry}")
    print(f"  Plan:       {plan}")
    if create_owner:
        print(f"  Owner:      {owner_name} <{owner_email}>")

    if not prompt_bool("Create tenant with these details?", default=True):
        print("Cancelled.")
        sys.exit(3)

    plan_tier = validate_plan(plan)

    result = await create_tenant(
        db=db,
        name=name,
        slug=slug,
        phone=phone,
        email=email,
        timezone=timezone,
        industry=industry,
        plan_tier=plan_tier,
        address=address,
        website=website,
        owner_email=owner_email,
        owner_name=owner_name,
        dry_run=dry_run,
    )
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.scripts.create_tenant",
        description="Interactive tenant onboarding for Owlbell.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Interactive wizard
  %(prog)s --name "Acme" --slug acme    # Quick mode
  %(prog)s --list                       # Show existing tenants
  %(prog)s --dry-run --name "Test"      # Validate without DB write
        """.strip(),
    )
    parser.add_argument("--name", help="Business display name")
    parser.add_argument("--slug", help="URL-safe identifier")
    parser.add_argument("--phone", help="Business phone (E.164)")
    parser.add_argument("--email", help="Business email")
    parser.add_argument("--timezone", default="America/New_York", help="Timezone")
    parser.add_argument("--industry", default="other", help="Industry category")
    parser.add_argument("--plan", default="starter", help="Plan tier")
    parser.add_argument("--address", help="Business address")
    parser.add_argument("--website", help="Website URL")
    parser.add_argument("--owner-email", help="Owner account email")
    parser.add_argument("--owner-name", help="Owner full name")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, no DB write")
    parser.add_argument("--list", action="store_true", help="List existing tenants")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return parser


async def _async_main(argv: Optional[list] = None) -> int:
    """Async main entry."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    session, engine = await _db_session()

    try:
        # Ensure plan definitions exist
        async with session.begin():
            await seed_plan_definitions(session)

        # -- List mode --------------------------------------------------------
        if args.list:
            async with session.begin():
                tenants = await list_existing_tenants(session)
            if not tenants:
                print("No tenants found.")
            else:
                print(f"\n{'Slug':<20} {'Name':<25} {'Plan':<12} {'Status'}")
                print("-" * 70)
                for t in tenants:
                    print(f"{t['slug']:<20} {t['name']:<25} {t['plan']:<12} {t['status']}")
                print(f"\nTotal: {len(tenants)} tenant(s)\n")
            return 0

        # -- Determine mode ---------------------------------------------------
        quick_mode = all([args.name, args.slug])

        if quick_mode:
            # Validate inputs
            try:
                validate_slug(args.slug)
                validate_phone(args.phone or "+1-000-000-0000")
                if args.email:
                    validate_email(args.email)
                plan_tier = validate_plan(args.plan)
            except ValueError as exc:
                print(f"Validation error: {exc}")
                return 1

            result = await create_tenant(
                db=session,
                name=args.name,
                slug=args.slug,
                phone=validate_phone(args.phone or f"+1-555-{secrets.randbelow(9000)+1000:04d}"),
                email=validate_email(args.email or f"contact@{args.slug}.example.com"),
                timezone=args.timezone,
                industry=validate_industry(args.industry),
                plan_tier=plan_tier,
                address=args.address,
                website=args.website,
                owner_email=args.owner_email,
                owner_name=args.owner_name,
                dry_run=args.dry_run,
            )
        else:
            # Interactive mode
            result = await interactive_mode(session, dry_run=args.dry_run)

        # -- Output -------------------------------------------------------------
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print_summary(result)

        return 0

    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    except Exception as exc:
        logger.error("create_tenant.failed", error=str(exc))
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2
    finally:
        await session.close()
        await engine.dispose()


def main(argv: Optional[list] = None) -> int:
    """Synchronous entry point."""
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    sys.exit(main())
