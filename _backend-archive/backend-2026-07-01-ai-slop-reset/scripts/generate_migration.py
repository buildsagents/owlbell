"""Auto-generate Alembic migration by introspecting SQLAlchemy models.

Usage: python scripts/generate_migration.py
Output: prints migration content to stdout.

Pipe to a file or review before committing.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from path_setup import ensure_import_paths

ensure_import_paths()

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from backend.db.models import Base


def _col_type(col: sa.Column) -> str:
    t = col.type
    if isinstance(t, postgresql.UUID):
        return "postgresql.UUID(as_uuid=True)"
    if isinstance(t, postgresql.JSONB):
        return "postgresql.JSONB"
    if isinstance(t, postgresql.INET):
        return "postgresql.INET"
    if isinstance(t, postgresql.TSVECTOR):
        return "postgresql.TSVECTOR"
    if isinstance(t, sa.Numeric):
        return f"sa.Numeric({t.precision}, {t.scale})" if t.precision is not None else "sa.Numeric()"
    if isinstance(t, sa.BigInteger):
        return "sa.BigInteger()"
    if isinstance(t, sa.Integer):
        return "sa.Integer()"
    if isinstance(t, sa.String):
        return f"sa.String({t.length})" if t.length else "sa.String()"
    if isinstance(t, sa.Text):
        return "sa.Text()"
    if isinstance(t, sa.Boolean):
        return "sa.Boolean()"
    if isinstance(t, sa.DateTime):
        return "sa.DateTime()"
    if isinstance(t, sa.Date):
        return "sa.Date()"
    if isinstance(t, sa.Time):
        return "sa.Time()"
    if isinstance(t, sa.Float):
        return "sa.Float()"
    if isinstance(t, sa.Enum):
        values = [e.value if hasattr(e, "value") else str(e) for e in t.enums]
        return f"sa.Enum({', '.join(repr(v) for v in values)}, name='{t.name}')"
    return f"sa.{type(t).__name__}()"


def _col_kw(col: sa.Column) -> dict:
    kw = {}
    if col.nullable is not None:
        kw["nullable"] = col.nullable
    if col.primary_key:
        kw["primary_key"] = True
    if col.unique:
        kw["unique"] = True
    if col.index:
        kw["index"] = True
    if col.comment:
        kw["comment"] = repr(col.comment)
    if col.autoincrement is True:
        kw["autoincrement"] = True
    fks = list(col.foreign_keys)
    if fks:
        ref = f"{fks[0].column.table.name}.{fks[0].column.name}"
        kw["sa.ForeignKey"] = f"'[\"{ref}\", ondelete={repr(fks[0].ondelete) if fks[0].ondelete else 'None'}]'"
    if col.server_default and not isinstance(col.default, sa.DefaultClause):
        from sqlalchemy import text
        sd = col.server_default
        if isinstance(sd.arg, str):
            kw["server_default"] = repr(sd.arg)
        else:
            kw["server_default"] = repr(str(sd.arg))
    return kw


def _table_sort_key(item) -> int:
    name = item[0]
    order = [
        "tenants", "users", "tenant_configs",
        "calls", "call_legs", "recordings",
        "conversations", "transcripts",
        "messages", "tool_calls",
        "prompts",
        "appointments", "routing_rules", "faq_entries",
        "business_hours", "holiday_schedules", "caller_profiles",
        "call_summaries", "notification_logs",
        "integration_connections", "oauth_tokens", "webhook_endpoints", "sync_logs",
        "usage_records", "audit_logs", "plan_definitions",
        "prompt_versions", "prompt_ab_tests",
        "onboarding_pipelines", "onboarding_steps", "onboarding_emails",
    ]
    return order.index(name) if name in order else 99


def generate():
    tables = sorted(Base.metadata.tables.items(), key=_table_sort_key)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        '"""create all tables from SQLAlchemy models',
        "",
        f"Revision ID: create_all_tables",
        "Revises: 8d8b122b9742",
        f"Create Date: {now}",
        '"""',
        "from typing import Sequence, Union",
        "",
        "import sqlalchemy as sa",
        "from alembic import op",
        "from sqlalchemy.dialects import postgresql",
        "",
        "# revision identifiers, used by Alembic.",
        "revision: str = 'create_all_tables'",
        "down_revision: Union[str, None] = '8d8b122b9742'",
        "branch_labels: Union[str, Sequence[str], None] = None",
        "depends_on: Union[str, Sequence[str], None] = None",
        "",
    ]

    # -- upgrade --
    lines.append("")
    lines.append("")
    lines.append("def upgrade() -> None:")
    lines.append('    """Create all tables."""')

    for name, table in tables:
        lines.append(f"    op.create_table('{name}',")
        for col in table.columns:
            col_str = f"        sa.Column('{col.name}', {_col_type(col)}"
            kw = _col_kw(col)
            if kw:
                parts = []
                for k, v in kw.items():
                    if k == "sa.ForeignKey":
                        parts.append(f"sa.ForeignKey({v})".replace("'[\"", "").replace("\"]'", ""))
                    else:
                        parts.append(f"{k}={v}")
                    col_str += ", " + ", ".join(parts)
            col_str += "),"
            lines.append(col_str)

        # CheckConstraints
        for c in table.constraints:
            if isinstance(c, sa.CheckConstraint):
                lines.append(f"        sa.CheckConstraint(\"{c.sqltext}\", name='{c.name}'),")

        # UniqueConstraints
        for c in table.constraints:
            if isinstance(c, sa.UniqueConstraint):
                cols = ", ".join(c.columns.keys())
                lines.append(f"        sa.UniqueConstraint('{cols}', name='{c.name}'),")

        lines.append("    )")
        lines.append("")

    # -- downgrade --
    lines.append("")
    lines.append("")
    lines.append("def downgrade() -> None:")
    lines.append('    """Drop all tables."""')
    for name in reversed([n for n, _ in sorted(tables, key=_table_sort_key)]):
        lines.append(f"    op.drop_table('{name}')")

    return "\n".join(lines)


if __name__ == "__main__":
    print(generate())
