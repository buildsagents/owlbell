"""
One-time ETL: Supabase product tables -> main PostgreSQL.

Reads from SUPABASE_DATABASE_URL (Postgres connection to Supabase project).
Writes tenant_integrations + calls into the main Owlbell database.

Tables migrated:
  - organizations + agents  -> tenant_integrations (matched by business name/email)
  - subscriptions           -> tenant_integrations stripe fields
  - calls                   -> calls (by provider_call_id / retell_call_id)

Usage:
    SUPABASE_DATABASE_URL=postgresql://... DATABASE_URL=postgresql+asyncpg://... \\
        python -m backend.scripts.migrate_supabase_etl --dry-run

    python -m backend.scripts.migrate_supabase_etl --apply
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from path_setup import ensure_import_paths

ensure_import_paths()

from backend.config import get_settings
from backend.db.models.call import Call
from backend.db.models.enums import AIModel, CallDirection, CallStatus
from backend.db.models.tenant import Tenant
from backend.db.tenant_integrations_service import upsert_for_tenant


def _plan_map(tier: str) -> str:
    return {"basic": "BASIC", "pro": "PRO", "pro_plus": "PRO_PLUS"}.get(tier or "", "FREE")


async def _fetch_supabase_rows(supabase_url: str, sql: str) -> list[dict[str, Any]]:
    """Run a read-only query against Supabase via sync psycopg2 in a thread."""
    import psycopg2
    import psycopg2.extras

    def _run() -> list[dict[str, Any]]:
        conn = psycopg2.connect(supabase_url)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    return await asyncio.to_thread(_run)


async def _match_tenant(db: AsyncSession, org: dict[str, Any]) -> Optional[Tenant]:
    name = (org.get("name") or "").strip()
    if name:
        result = await db.execute(
            select(Tenant).where(Tenant.name.ilike(name), Tenant.deleted_at.is_(None))
        )
        tenant = result.scalar_one_or_none()
        if tenant:
            return tenant
    return None


async def run(*, apply: bool, supabase_url: str) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database.url, echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    orgs = await _fetch_supabase_rows(
        supabase_url,
        "SELECT id, name, industry, timezone, created_at FROM organizations ORDER BY created_at",
    )
    agents = await _fetch_supabase_rows(
        supabase_url,
        """
        SELECT org_id, voice_provider, provider_agent_id, phone_number
        FROM agents ORDER BY created_at
        """,
    )
    subs = await _fetch_supabase_rows(
        supabase_url,
        """
        SELECT org_id, stripe_customer_id, stripe_subscription_id, plan_tier, status
        FROM subscriptions
        """,
    )
    sb_calls = await _fetch_supabase_rows(
        supabase_url,
        """
        SELECT org_id, provider_call_id, caller_number, duration_seconds,
               status, summary, created_at
        FROM calls ORDER BY created_at
        """,
    )

    agents_by_org = {a["org_id"]: a for a in agents}
    subs_by_org = {s["org_id"]: s for s in subs}

    stats = {"integrations": 0, "calls_imported": 0, "calls_skipped": 0, "unmatched_orgs": 0}

    async with session_maker() as db:
        for org in orgs:
            tenant = await _match_tenant(db, org)
            if not tenant:
                stats["unmatched_orgs"] += 1
                print(f"[skip] no Postgres tenant for Supabase org {org.get('name')} ({org['id']})")
                continue

            agent = agents_by_org.get(org["id"], {})
            sub = subs_by_org.get(org["id"], {})
            fields = {
                "voice_provider": agent.get("voice_provider") or "retell",
                "retell_agent_id": agent.get("provider_agent_id"),
                "retell_phone_number": agent.get("phone_number"),
                "stripe_customer_id": sub.get("stripe_customer_id"),
                "stripe_subscription_id": sub.get("stripe_subscription_id"),
            }
            print(f"[{'apply' if apply else 'dry-run'}] integrations -> {tenant.slug}: {fields}")
            if apply:
                await upsert_for_tenant(db, tenant.id, **fields)
            stats["integrations"] += 1

        for sb_call in sb_calls:
            provider_call_id = sb_call.get("provider_call_id")
            if not provider_call_id:
                stats["calls_skipped"] += 1
                continue

            existing = await db.execute(
                select(Call).where(Call.retell_call_id == provider_call_id)
            )
            if existing.scalar_one_or_none():
                stats["calls_skipped"] += 1
                continue

            org = next((o for o in orgs if o["id"] == sb_call["org_id"]), None)
            if not org:
                stats["calls_skipped"] += 1
                continue
            tenant = await _match_tenant(db, org)
            if not tenant:
                stats["calls_skipped"] += 1
                continue

            print(
                f"[{'apply' if apply else 'dry-run'}] call {provider_call_id} -> tenant {tenant.slug}"
            )
            if apply:
                call = Call(
                    id=uuid4(),
                    tenant_id=tenant.id,
                    call_sid=provider_call_id,
                    retell_call_id=provider_call_id,
                    direction=CallDirection.INBOUND,
                    caller_number=sb_call.get("caller_number") or "unknown",
                    destination_number=tenant.business_phone or "unknown",
                    status=CallStatus.COMPLETED,
                    ai_handled=True,
                    ai_model_used=AIModel.RETELL_AI,
                    duration_seconds=sb_call.get("duration_seconds") or 0,
                    transcript_summary=sb_call.get("summary"),
                    started_at=sb_call.get("created_at") or datetime.utcnow(),
                    metadata_json={"migrated_from": "supabase", "provider_call_id": provider_call_id},
                )
                db.add(call)
            stats["calls_imported"] += 1

        if apply:
            await db.commit()

    await engine.dispose()
    print("ETL complete:", stats)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Supabase product data to main Postgres")
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry-run)")
    parser.add_argument(
        "--supabase-url",
        default=os.environ.get("SUPABASE_DATABASE_URL", ""),
        help="Supabase Postgres URL (postgresql://...)",
    )
    args = parser.parse_args()

    if not args.supabase_url:
        print("ERROR: set SUPABASE_DATABASE_URL or pass --supabase-url", file=sys.stderr)
        return 1

    return asyncio.run(run(apply=args.apply, supabase_url=args.supabase_url))


if __name__ == "__main__":
    raise SystemExit(main())