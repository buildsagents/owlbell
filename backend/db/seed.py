"""
Owlbell — Database Seed CLI.

Location: backend/db/seed.py

Command-line interface for seeding demo data and resetting the database.
All operations are idempotent and safe to run multiple times.

Usage::

    # Seed demo data (Smith Dental Clinic)
    python -m backend.db.seed --demo

    # Reset (truncate) all data — requires --force
    python -m backend.db.seed --reset --force

    # Reset and re-seed
    python -m backend.db.seed --reset --force --demo

    # Show help
    python -m backend.db.seed --help

    # Dry-run (show what would be seeded)
    python -m backend.db.seed --demo --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.db.models import Base
from backend.db.seed_data import (
    PLAN_DEFINITIONS,
    FAQ_ENTRIES,
    ROUTING_RULES,
    BUSINESS_HOURS,
    HOLIDAYS,
    PROMPTS,
    DEMO_TENANT_DATA,
    DEMO_USER_DATA,
    _SAMPLE_CALLS,
    _SAMPLE_APPOINTMENTS,
    seed_all_demo_data,
    reset_all_data,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("seed")

# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------


def _get_engine():
    """Create an async engine from settings."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )


async def _get_session() -> AsyncSession:
    """Create a fresh async session for seeding."""
    engine = _get_engine()
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return session_maker(), engine


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.db.seed",
        description="Seed or reset Owlbell database data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --demo                  Seed demo data (idempotent)
  %(prog)s --reset --force         Truncate all tables
  %(prog)s --reset --force --demo  Clean slate + re-seed
  %(prog)s --demo --dry-run        Preview what would be seeded
  %(prog)s --plans-only            Seed only plan definitions
        """.strip(),
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Seed the full demo dataset (Smith Dental Clinic).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate all tenant-scoped tables. Requires --force.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Confirm destructive operations (reset).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be seeded without touching the database.",
    )
    parser.add_argument(
        "--plans-only",
        action="store_true",
        help="Seed only plan definitions (global table).",
    )
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Create all tables from SQLAlchemy models before seeding.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON (for CI/automation).",
    )
    return parser


# ---------------------------------------------------------------------------
# Dry-run preview
# ---------------------------------------------------------------------------


def _preview_seed() -> None:
    """Print a preview of what the seed operation would create."""
    print("=" * 60)
    print("DRY RUN — Demo data seed preview")
    print("=" * 60)

    print("\n--- Plan Definitions ---")
    for p in PLAN_DEFINITIONS:
        print(f"  [{p['plan_tier'].value:14s}] {p['display_name']} — {p['description'][:50]}...")

    print("\n--- Demo Tenant ---")
    t = DEMO_TENANT_DATA
    print(f"  Name:        {t['business_name']}")
    print(f"  Slug:        {t['slug']}")
    print(f"  Phone:       {t['business_phone']}")
    print(f"  Email:       {t['business_email']}")
    print(f"  Timezone:    {t['business_timezone']}")
    print(f"  Address:     {t['business_address']}")
    print(f"  Plan:        {t['plan_tier'].value}")
    print(f"  Industry:    {t['industry']}")

    print("\n--- Demo User ---")
    u = DEMO_USER_DATA
    print(f"  Name:        {u['first_name']} {u['last_name']}")
    print(f"  Email:       {u['email']}")
    print(f"  Role:        {u['role'].value}")
    print(f"  Phone:       {u['phone']}")

    print(f"\n--- FAQ Entries ({len(FAQ_ENTRIES)}) ---")
    for f in FAQ_ENTRIES:
        print(f"  [{f['category']:12s}] {f['question'][:55]}...")

    print(f"\n--- Routing Rules ({len(ROUTING_RULES)}) ---")
    for r in ROUTING_RULES:
        print(f"  [P{r['priority']:3d}] {r['name']} -> {r['action'].value}")

    print(f"\n--- Business Hours ({len(BUSINESS_HOURS)}) ---")
    for b in BUSINESS_HOURS:
        status = "CLOSED" if b["is_closed"] else f"{b['open_time']} - {b['close_time']}"
        print(f"  {b['day_of_week']:10s} {status}")

    print(f"\n--- Holidays ({len(HOLIDAYS)}) ---")
    for h in HOLIDAYS:
        status = "CLOSED" if h["is_closed"] else f"{h['open_time']} - {h['close_time']}"
        print(f"  {h['date']}  {h['name'][:25]:25s} {status}")

    print(f"\n--- AI Prompts ({len(PROMPTS)}) ---")
    for p in PROMPTS:
        print(f"  [{p['prompt_type']:10s}] {p['name'][:45]}")

    print(f"\n--- Sample Calls ({len(_SAMPLE_CALLS)}) ---")
    call_types = {}
    for c in _SAMPLE_CALLS:
        intent = c.get("intent_detected", "unknown")
        call_types[intent] = call_types.get(intent, 0) + 1
    for intent, count in sorted(call_types.items()):
        print(f"  {intent}: {count}")

    print(f"\n--- Sample Appointments ({len(_SAMPLE_APPOINTMENTS)}) ---")
    for a in _SAMPLE_APPOINTMENTS:
        print(f"  {a['scheduled_date']} {a['start_time']}  {a['title'][:30]:30s} [{a['status'].value}]")

    print("\n" + "=" * 60)
    print("End of preview — no database changes made.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def _async_main(argv: Optional[list] = None) -> int:
    """Async main entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # -- Validate arguments ---------------------------------------------------
    if not any([args.demo, args.reset, args.plans_only, args.dry_run]):
        parser.print_help()
        return 0

    if args.reset and not args.force:
        print("ERROR: --reset requires --force to confirm the destructive operation.")
        print("Run with --force to proceed.")
        return 1

    if args.dry_run:
        _preview_seed()
        return 0

    # -- Dry-run preview before actual seed -----------------------------------
    if args.demo and not args.reset:
        _preview_seed()
        print("\nProceeding with seed in 2 seconds...\n")
        await asyncio.sleep(2)

    # -- Connect to database --------------------------------------------------
    settings = get_settings()
    logger.info("seed.db_connect", host=settings.database.host, db=settings.database.db)

    session, engine = await _get_session()

    try:
        # Optionally create tables
        if args.create_tables:
            logger.info("seed.creating_tables")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("seed.tables_created")

        # -- Reset (truncate) -------------------------------------------------
        if args.reset:
            if not args.force:
                print("ERROR: --reset requires --force")
                return 1
            async with session.begin():
                await reset_all_data(session)
            print("All tenant-scoped data has been truncated.")

        # -- Seed --------------------------------------------------------------
        if args.plans_only:
            from backend.db.seed_data import seed_plan_definitions
            async with session.begin():
                await seed_plan_definitions(session)
            print("Plan definitions seeded successfully.")
            return 0

        if args.demo:
            async with session.begin():
                summary = await seed_all_demo_data(session)

            # Print results
            print("\n" + "=" * 60)
            print("Demo data seeded successfully!")
            print("=" * 60)
            print(f"\nTenant:      {summary['tenant_slug']} ({summary['tenant_id']})")
            print(f"Plan tier:   Starter")
            print(f"\nItems created:")
            print(f"  - Plan definitions:    {summary['plans_seeded']}")
            print(f"  - FAQ entries:         {summary['faq_entries']}")
            print(f"  - Routing rules:       {summary['routing_rules']}")
            print(f"  - Business hours:      {summary['business_hours']}")
            print(f"  - Holidays:            {summary['holidays']}")
            print(f"  - AI prompts:          {summary['prompts']}")
            print(f"  - Sample calls:        {summary['calls']}")
            print(f"  - Sample appointments: {summary['appointments']}")
            print(f"  - Conversation msgs:   {summary['messages']}")
            print(f"\nLogin credentials:")
            print(f"  Email:    {DEMO_USER_DATA['email']}")
            print(f"  Password: DemoPass123!")
            print(f"\nDashboard:  http://localhost:5173")
            print(f"API Docs:   http://localhost:8000/api/v1/docs")
            print("=" * 60)

            if args.json:
                import json
                print(json.dumps(summary, indent=2))

    except Exception as exc:
        logger.error("seed.failed", error=str(exc))
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    finally:
        await session.close()
        await engine.dispose()

    return 0


def main(argv: Optional[list] = None) -> int:
    """Synchronous entry point for the CLI."""
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    sys.exit(main())
