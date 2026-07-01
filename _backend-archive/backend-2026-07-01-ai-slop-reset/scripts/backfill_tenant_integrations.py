"""
Backfill tenant_integrations from tenants.config_json.

Usage:
    python -m backend.scripts.backfill_tenant_integrations
    python -m backend.scripts.backfill_tenant_integrations --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from path_setup import ensure_import_paths

ensure_import_paths()

from backend.config import get_settings
from backend.db.models.tenant import Tenant
from backend.db.tenant_integrations_service import sync_from_config_json


async def run(*, dry_run: bool) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database.url, echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    synced = 0
    async with session_maker() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.deleted_at.is_(None))
        )
        tenants = result.scalars().all()
        for tenant in tenants:
            if dry_run:
                cfg = tenant.config_json or {}
                if any(
                    cfg.get(k)
                    for k in (
                        "retell_agent_id",
                        "stripe_customer_id",
                        "retell_phone_number",
                        "retell_phone",
                        "assigned_phone",
                    )
                ):
                    synced += 1
                    print(f"[dry-run] would sync tenant {tenant.slug} ({tenant.id})")
                continue

            await sync_from_config_json(db, tenant)
            synced += 1
            print(f"synced tenant {tenant.slug} ({tenant.id})")

        if not dry_run:
            await db.commit()

    await engine.dispose()
    print(f"Done — {synced} tenant(s) {'would be ' if dry_run else ''}synced.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill tenant_integrations table")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    return asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())