"""
Alembic async migration environment.

Location: backend/db/migrations/env.py

Auto-detects schema changes from SQLAlchemy models.
Uses DATABASE_URL from project configuration (config.py).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Import config and all models for Alembic auto-detection ─────

from backend.config import get_settings
from backend.db.models import Base  # noqa: F401
from backend.db.models import *  # noqa: F401,F403

# ── Alembic Config ──────────────────────────────────────────────

config = context.config

# Setup Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


# ── Database URL ────────────────────────────────────────────────


def get_database_url() -> str:
    """Get async database URL from project configuration."""
    return get_settings().database_url


# ── Revision Directives ─────────────────────────────────────────


def process_revision_directives(context, revision, directives):
    """Custom revision processing to skip empty migrations.

    If autogenerate produces no schema changes, the migration script
    is discarded and a message is printed.
    """
    if directives:
        script = directives[0]
        if script.upgrade_ops.is_empty():
            directives[:] = []
            print("No schema changes detected — migration not generated.")


# ── Offline Migrations ──────────────────────────────────────────


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL scripts).

    Used for generating SQL migration scripts that can be reviewed
    and applied manually by a DBA.
    """
    url = get_database_url().replace("+asyncpg", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Enable autogenerate support
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online Migrations ───────────────────────────────────────────


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations with proper configuration."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        render_as_batch=True,
        user_module_prefix="None",
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations."""
    asyncio.run(run_async_migrations())


# ── Entry Point ─────────────────────────────────────────────────

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
