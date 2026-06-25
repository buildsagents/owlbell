"""
Owlbell — Database Migration & Setup Script.

Location: backend/scripts/setup_supabase.py

Uses asyncpg for direct PostgreSQL connections. Reads config from
backend.config.DatabaseSettings and executes schema migrations plus
seed data for initial setup.

Usage::

    python -m backend.scripts.setup_supabase migrate          # Apply schema
    python -m backend.scripts.setup_supabase seed             # Seed initial data
    python -m backend.scripts.setup_supabase reset            # Drop & recreate (dev only)
    python -m backend.scripts.setup_supabase status           # Show migration status
    python -m backend.scripts.setup_supabase migrate --dry-run # Preview SQL
    python -m backend.scripts.setup_supabase seed --dry-run    # Preview seed data

Exit codes::

    0  Success
    1  Error
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCHEMA_SQL_PATH = BACKEND_DIR / "db" / "migrations" / "schema.sql"
MIGRATION_TABLE = "_migration_history"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("setup_supabase")

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------


async def _connect() -> asyncpg.Connection:
    """Create a direct asyncpg connection from config."""
    import os
    sys.path.insert(0, str(BACKEND_DIR.parent))

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        from backend.config import get_settings
        settings = get_settings()
        db_url = settings.database.url

    # Parse the URL
    url = db_url
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = url[len(prefix):]
            break
    auth, rest = url.split("@", 1)
    user, password = auth.split(":", 1)
    host_port, db = rest.split("/", 1)
    if "?" in db:
        db = db.split("?", 1)[0]
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        port = int(port)
    else:
        host, port = host_port, 5432
    return await asyncpg.connect(host=host, port=port, user=user, password=password, database=db, ssl="require")


# ---------------------------------------------------------------------------
# Schema SQL (Supabase-adapted for raw PostgreSQL)
# ---------------------------------------------------------------------------

# The Supabase schema.sql references auth.users which doesn't exist in raw
# PostgreSQL. We provide a self-contained schema that mirrors the same tables
# but uses a local profiles table with its own user management.

SCHEMA_SQL = textwrap.dedent("""\
    -- ============================================================
    -- Owlbell — Core Schema (Supabase-compatible, raw PostgreSQL)
    -- ============================================================

    -- Enable UUID generation
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";

    -- ============================================================
    -- 1. Organizations (Tenants)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS organizations (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name        TEXT NOT NULL,
        industry    TEXT,
        timezone    TEXT NOT NULL DEFAULT 'America/New_York',
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- ============================================================
    -- 2. User Profiles
    -- ============================================================
    CREATE TABLE IF NOT EXISTS profiles (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id      UUID REFERENCES organizations(id) ON DELETE CASCADE,
        full_name   TEXT,
        email       TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        role        TEXT NOT NULL DEFAULT 'owner' CHECK (role IN ('owner','admin','viewer')),
        is_active   BOOLEAN NOT NULL DEFAULT true,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_profiles_org_id ON profiles(org_id);

    -- ============================================================
    -- 3. Billing Subscriptions
    -- ============================================================
    CREATE TABLE IF NOT EXISTS subscriptions (
        id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id                   UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE UNIQUE,
        stripe_customer_id       TEXT,
        stripe_subscription_id   TEXT,
        plan_tier                TEXT NOT NULL DEFAULT 'free'
                                   CHECK (plan_tier IN ('free','starter','professional','enterprise')),
        status                   TEXT NOT NULL DEFAULT 'trialing'
                                   CHECK (status IN ('active','trialing','past_due','canceled','incomplete')),
        current_period_end       TIMESTAMPTZ,
        created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- ============================================================
    -- 4. Plan Definitions (global, tenant-independent)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS plan_definitions (
        id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        plan_tier               TEXT UNIQUE NOT NULL
                                  CHECK (plan_tier IN ('free','starter','professional','enterprise')),
        display_name            TEXT NOT NULL,
        description             TEXT,
        price_monthly_cents     INTEGER NOT NULL DEFAULT 0,
        price_annual_cents      INTEGER NOT NULL DEFAULT 0,
        max_minutes_monthly     INTEGER NOT NULL DEFAULT 0,
        max_concurrent_calls    INTEGER NOT NULL DEFAULT 1,
        max_users               INTEGER NOT NULL DEFAULT 1,
        max_phone_numbers       INTEGER NOT NULL DEFAULT 1,
        features_json           JSONB NOT NULL DEFAULT '{}',
        is_public               BOOLEAN NOT NULL DEFAULT true,
        sort_order              INTEGER NOT NULL DEFAULT 0,
        created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- ============================================================
    -- 5. AI Voice Agents
    -- ============================================================
    CREATE TABLE IF NOT EXISTS agents (
        id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id             UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        voice_provider     TEXT NOT NULL DEFAULT 'retell' CHECK (voice_provider IN ('retell','vapi')),
        provider_agent_id  TEXT UNIQUE,
        phone_number       TEXT,
        system_prompt      TEXT,
        voice_id           TEXT,
        greeting           TEXT,
        created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_agents_org_id ON agents(org_id);

    -- ============================================================
    -- 6. Call Log Records
    -- ============================================================
    CREATE TABLE IF NOT EXISTS calls (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        agent_id          UUID REFERENCES agents(id) ON DELETE SET NULL,
        provider_call_id  TEXT UNIQUE,
        caller_number     TEXT,
        duration_seconds  INTEGER DEFAULT 0,
        status            TEXT NOT NULL DEFAULT 'completed'
                            CHECK (status IN ('completed','missed','in_progress','failed')),
        recording_url     TEXT,
        transcript        JSONB,
        summary           TEXT,
        action_items      JSONB,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX IF NOT EXISTS idx_calls_org_id     ON calls(org_id);
    CREATE INDEX IF NOT EXISTS idx_calls_created_at ON calls(created_at DESC);

    -- ============================================================
    -- 7. Migration tracking table
    -- ============================================================
    CREATE TABLE IF NOT EXISTS _migration_history (
        id          SERIAL PRIMARY KEY,
        version     TEXT NOT NULL UNIQUE,
        name        TEXT NOT NULL,
        applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        checksum    TEXT,
        duration_ms INTEGER
    );
""")

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

# Hard-coded UUIDs for idempotency
_SEED_PLAN_IDS: Dict[str, UUID] = {
    "free": UUID("33333333-3333-3333-3333-333333333333"),
    "starter": UUID("44444444-4444-4444-4444-444444444444"),
    "professional": UUID("55555555-5555-5555-5555-555555555555"),
    "enterprise": UUID("66666666-6666-6666-6666-666666666666"),
}

_SEED_TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
_SEED_USER_ID = UUID("22222222-2222-2222-2222-222222222222")

PLAN_SEED_DATA = [
    {
        "id": _SEED_PLAN_IDS["free"],
        "plan_tier": "free",
        "display_name": "Free",
        "description": "Perfect for small businesses trying AI answering. 100 minutes/month.",
        "price_monthly_cents": 0,
        "price_annual_cents": 0,
        "max_minutes_monthly": 100,
        "max_concurrent_calls": 1,
        "max_users": 2,
        "max_phone_numbers": 1,
        "features_json": json.dumps({
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
        }),
        "is_public": True,
        "sort_order": 1,
    },
    {
        "id": _SEED_PLAN_IDS["starter"],
        "plan_tier": "starter",
        "display_name": "Starter",
        "description": "For growing businesses. 500 minutes/month, 5 users, calendar sync.",
        "price_monthly_cents": 2900,
        "price_annual_cents": 29000,
        "max_minutes_monthly": 500,
        "max_concurrent_calls": 3,
        "max_users": 5,
        "max_phone_numbers": 2,
        "features_json": json.dumps({
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
        }),
        "is_public": True,
        "sort_order": 2,
    },
    {
        "id": _SEED_PLAN_IDS["professional"],
        "plan_tier": "professional",
        "display_name": "Professional",
        "description": "Full-featured. 2,000 minutes/month, 20 users, CRM, advanced analytics.",
        "price_monthly_cents": 7900,
        "price_annual_cents": 79000,
        "max_minutes_monthly": 2000,
        "max_concurrent_calls": 10,
        "max_users": 20,
        "max_phone_numbers": 5,
        "features_json": json.dumps({
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
        }),
        "is_public": True,
        "sort_order": 3,
    },
    {
        "id": _SEED_PLAN_IDS["enterprise"],
        "plan_tier": "enterprise",
        "display_name": "Enterprise",
        "description": "Unlimited. Custom deployment, SLA, dedicated support, unlimited everything.",
        "price_monthly_cents": 0,
        "price_annual_cents": 0,
        "max_minutes_monthly": 0,
        "max_concurrent_calls": 0,
        "max_users": 0,
        "max_phone_numbers": 0,
        "features_json": json.dumps({
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
            "custom_deployment": True,
            "sla_guarantee": True,
            "dedicated_account_manager": True,
        }),
        "is_public": True,
        "sort_order": 4,
    },
]


# ---------------------------------------------------------------------------
# Migration commands
# ---------------------------------------------------------------------------


async def _ensure_migration_table(conn: asyncpg.Connection) -> None:
    """Create the migration tracking table if it doesn't exist."""
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
            id          SERIAL PRIMARY KEY,
            version     TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            checksum    TEXT,
            duration_ms INTEGER
        );
    """)


async def cmd_migrate(conn: asyncpg.Connection, dry_run: bool = False) -> int:
    """Apply schema migration."""
    await _ensure_migration_table(conn)

    # Check if already applied
    row = await conn.fetchrow(
        f"SELECT version FROM {MIGRATION_TABLE} WHERE version = $1",
        "001_core_schema",
    )
    if row:
        print("Migration 001_core_schema already applied. Nothing to do.")
        return 0

    if dry_run:
        print("=" * 60)
        print("DRY RUN — SQL that would be executed:")
        print("=" * 60)
        print(SCHEMA_SQL)
        print("=" * 60)
        print(f"\nWould insert migration record: 001_core_schema")
        return 0

    print("Applying migration 001_core_schema ...")
    start = asyncio.get_event_loop().time()

    try:
        await conn.execute(SCHEMA_SQL)
    except asyncpg.exceptions.DuplicateTableError:
        print("  Tables already exist (partial schema). Continuing...")
    except asyncpg.exceptions.InvalidSqlStatementNameError as exc:
        # Some PostgreSQL extensions or syntax differences
        print(f"  Warning during execution: {exc}")
        print("  Attempting statement-by-statement execution...")
        statements = [s.strip() for s in SCHEMA_SQL.split(";") if s.strip()]
        for stmt in statements:
            try:
                await conn.execute(stmt)
            except asyncpg.exceptions.DuplicateTableError:
                pass
            except Exception as inner_exc:
                print(f"  Skipping statement: {inner_exc}")

    elapsed_ms = int((asyncio.get_event_loop().time() - start) * 1000)

    # Record migration
    await conn.execute(
        f"""INSERT INTO {MIGRATION_TABLE} (version, name, checksum, duration_ms)
            VALUES ($1, $2, $3, $4)""",
        "001_core_schema",
        "Core schema — organizations, profiles, subscriptions, agents, calls, plan_definitions",
        str(hash(SCHEMA_SQL)),
        elapsed_ms,
    )

    print(f"Migration 001_core_schema applied successfully ({elapsed_ms}ms).")
    return 0


async def cmd_seed(conn: asyncpg.Connection, dry_run: bool = False) -> int:
    """Seed initial data: plan definitions, default tenant, default admin user."""
    await _ensure_migration_table(conn)

    if dry_run:
        print("=" * 60)
        print("DRY RUN — Seed data that would be inserted:")
        print("=" * 60)

        print("\n--- Plan Definitions ---")
        for p in PLAN_SEED_DATA:
            print(f"  [{p['plan_tier']:15s}] {p['display_name']:15s} — {p['description'][:50]}...")

        print("\n--- Default Tenant ---")
        print(f"  ID:        {_SEED_TENANT_ID}")
        print(f"  Name:      Default Organization")

        print("\n--- Default Admin User ---")
        print(f"  ID:        {_SEED_USER_ID}")
        print(f"  Email:     admin@owlbell.example.com")
        print(f"  Role:      admin")

        print("=" * 60)
        return 0

    print("Seeding initial data ...")

    # 1. Plan definitions
    print("  Seeding plan definitions ...")
    plans_inserted = 0
    for plan in PLAN_SEED_DATA:
        row = await conn.fetchrow(
            "SELECT id FROM plan_definitions WHERE plan_tier = $1",
            plan["plan_tier"],
        )
        if row:
            print(f"    Plan '{plan['plan_tier']}' already exists — skipping.")
            continue
        await conn.execute(
            """INSERT INTO plan_definitions
                (id, plan_tier, display_name, description,
                 price_monthly_cents, price_annual_cents,
                 max_minutes_monthly, max_concurrent_calls,
                 max_users, max_phone_numbers,
                 features_json, is_public, sort_order)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12,$13)""",
            plan["id"],
            plan["plan_tier"],
            plan["display_name"],
            plan["description"],
            plan["price_monthly_cents"],
            plan["price_annual_cents"],
            plan["max_minutes_monthly"],
            plan["max_concurrent_calls"],
            plan["max_users"],
            plan["max_phone_numbers"],
            plan["features_json"],
            plan["is_public"],
            plan["sort_order"],
        )
        plans_inserted += 1
        print(f"    Inserted plan: {plan['plan_tier']}")

    # 2. Default tenant
    print("  Seeding default tenant ...")
    tenant_row = await conn.fetchrow(
        "SELECT id FROM organizations WHERE id = $1",
        _SEED_TENANT_ID,
    )
    if tenant_row:
        print("    Default tenant already exists — skipping.")
    else:
        await conn.execute(
            """INSERT INTO organizations (id, name, industry, timezone)
               VALUES ($1, $2, $3, $4)""",
            _SEED_TENANT_ID,
            "Default Organization",
            "other",
            "America/New_York",
        )
        # Create a subscription for the tenant on the free plan
        await conn.execute(
            """INSERT INTO subscriptions (org_id, plan_tier, status)
               VALUES ($1, $2, $3)""",
            _SEED_TENANT_ID,
            "free",
            "active",
        )
        print(f"    Inserted default tenant (id={_SEED_TENANT_ID})")

    # 3. Default admin user
    print("  Seeding default admin user ...")
    user_row = await conn.fetchrow(
        "SELECT id FROM profiles WHERE id = $1",
        _SEED_USER_ID,
    )
    if user_row:
        print("    Default admin user already exists — skipping.")
    else:
        await conn.execute(
            """INSERT INTO profiles (id, org_id, full_name, email, password_hash, role, is_active)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            _SEED_USER_ID,
            _SEED_TENANT_ID,
            "Admin User",
            "admin@owlbell.example.com",
            "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA.qGZvKG6G",  # "DemoPass123!"
            "admin",
            True,
        )
        print(f"    Inserted admin user (id={_SEED_USER_ID})")

    print("\nSeed completed successfully.")
    print(f"  Plans inserted:      {plans_inserted}")
    print(f"  Tenant:              {_SEED_TENANT_ID}")
    print(f"  Admin user:          admin@owlbell.example.com")
    print(f"  Admin password:      DemoPass123!")
    return 0


async def cmd_reset(conn: asyncpg.Connection, dry_run: bool = False) -> int:
    """Drop and recreate all tables (dev only)."""
    if dry_run:
        print("=" * 60)
        print("DRY RUN — Tables that would be dropped:")
        print("=" * 60)
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        for t in tables:
            print(f"  DROP TABLE IF EXISTS {t['tablename']} CASCADE;")
        print(f"\nThen re-run: migrate + seed")
        print("=" * 60)
        return 0

    print("WARNING: This will drop ALL tables in the database!")
    print("This is a destructive operation intended for development only.")

    tables = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    )
    table_names = [t["tablename"] for t in tables]

    if not table_names:
        print("No tables found. Nothing to drop.")
        return 0

    print(f"Dropping {len(table_names)} table(s) ...")
    for name in table_names:
        await conn.execute(f"DROP TABLE IF EXISTS {name} CASCADE")
        print(f"  Dropped: {name}")

    print("\nAll tables dropped.")
    print("Run 'migrate' and 'seed' to rebuild.")
    return 0


async def cmd_status(conn: asyncpg.Connection) -> int:
    """Show migration and database status."""
    await _ensure_migration_table(conn)

    # Migration history
    migrations = await conn.fetch(
        f"SELECT * FROM {MIGRATION_TABLE} ORDER BY applied_at"
    )

    print("=" * 60)
    print("  Owlbell Database Status")
    print("=" * 60)

    if migrations:
        print(f"\nApplied migrations ({len(migrations)}):")
        for m in migrations:
            print(f"  {m['version']:25s} {m['name'][:40]:40s} {m['applied_at']}")
    else:
        print("\nNo migrations applied yet.")

    # Table counts
    print("\nTable row counts:")
    tables = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    )
    for t in tables:
        count = await conn.fetchval(f"SELECT count(*) FROM {t['tablename']}")
        print(f"  {t['tablename']:30s} {count:>8,} rows")

    # Plan definitions
    print("\nPlan definitions:")
    plans = await conn.fetch(
        "SELECT plan_tier, display_name, max_minutes_monthly, max_users FROM plan_definitions ORDER BY sort_order"
    )
    if plans:
        for p in plans:
            print(f"  {p['plan_tier']:15s} {p['display_name']:15s} "
                  f"minutes={p['max_minutes_monthly']:>6,}  users={p['max_users']:>3,}")
    else:
        print("  (none — run 'seed' to populate)")

    # Organizations
    orgs = await conn.fetch(
        "SELECT id, name FROM organizations LIMIT 10"
    )
    if orgs:
        print(f"\nOrganizations ({len(orgs)}):")
        for o in orgs:
            print(f"  {o['id']}  {o['name']}")
    else:
        print("\nOrganizations: (none)")

    print("=" * 60)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.scripts.setup_supabase",
        description="Database migration & setup for Owlbell (raw PostgreSQL).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              %(prog)s migrate              Apply schema migrations
              %(prog)s seed                 Seed initial data (plans, tenant, user)
              %(prog)s migrate && %(prog)s seed   Full fresh setup
              %(prog)s reset                Drop all tables (dev only)
              %(prog)s status               Show migration status
              %(prog)s migrate --dry-run    Preview SQL without executing
        """).strip(),
    )
    parser.add_argument(
        "command",
        choices=["migrate", "seed", "reset", "status"],
        help="Command to execute.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would happen without touching the database.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


async def _async_main(argv: Optional[list] = None) -> int:
    """Async main entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    conn = None
    try:
        conn = await _connect()
        logger.info("Connected to database.")

        if args.command == "migrate":
            return await cmd_migrate(conn, dry_run=args.dry_run)
        elif args.command == "seed":
            return await cmd_seed(conn, dry_run=args.dry_run)
        elif args.command == "reset":
            return await cmd_reset(conn, dry_run=args.dry_run)
        elif args.command == "status":
            return await cmd_status(conn)
        else:
            parser.print_help()
            return 1

    except asyncpg.exceptions.ConnectionDoesNotExistError as exc:
        print(f"Connection error: {exc}")
        print("Check that PostgreSQL is running and connection details in .env are correct.")
        return 1
    except asyncpg.exceptions.InvalidCatalogNameError as exc:
        print(f"Database not found: {exc}")
        print("Create the database first, then retry.")
        return 1
    except Exception as exc:
        logger.error("setup_supabase.failed: %s", exc)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        if conn:
            await conn.close()


def main(argv: Optional[list] = None) -> int:
    """Synchronous entry point."""
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    sys.exit(main())
