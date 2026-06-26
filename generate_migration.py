"""Auto-generate Alembic migration by introspecting SQLAlchemy models.

Usage: python generate_migration.py (from project root)
Output: writes migration file to backend/db/migrations/versions/
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from backend.db.models import Base


def _col_type(col):
    t = col.type
    from sqlalchemy import Enum as SAEnum
    # Check Enum FIRST (it's a subclass of String)
    if isinstance(t, SAEnum):
        values = [e.value if hasattr(e, "value") else str(e) for e in t.enums]
        return f"sa.Enum({', '.join(repr(v) for v in values)}, name='{t.name}')"
    if isinstance(t, postgresql.UUID):
        return "postgresql.UUID(as_uuid=True)"
    if isinstance(t, postgresql.JSONB):
        return "postgresql.JSONB()"
    if isinstance(t, postgresql.INET):
        return "postgresql.INET()"
    if isinstance(t, postgresql.TSVECTOR):
        return "postgresql.TSVECTOR()"
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
    return f"sa.{type(t).__name__}()"


def _col_kw(col):
    kw = {}
    if col.nullable is not None and not col.nullable:
        kw["nullable"] = False
    if col.primary_key:
        kw["primary_key"] = True
    if col.unique:
        kw["unique"] = True
    if col.comment:
        kw["comment"] = repr(col.comment)
    fks = list(col.foreign_keys)
    if fks:
        ref = f'"{fks[0].column.table.name}.{fks[0].column.name}"'
        ondel = fks[0].ondelete
        if ondel:
            kw["fk"] = f"sa.ForeignKey({ref}, ondelete='{ondel}')"
        else:
            kw["fk"] = f"sa.ForeignKey({ref})"
    return kw


TABLE_ORDER = [
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


def _sort_key(item):
    name = item[0]
    return TABLE_ORDER.index(name) if name in TABLE_ORDER else 99


def _server_default(col):
    sd = col.server_default
    if sd is None:
        return None
    from sqlalchemy import TextClause
    arg = sd.arg
    if arg is None:
        return None
    if isinstance(arg, str):
        return repr(arg)
    if isinstance(arg, TextClause):
        text_val = str(arg.text) if hasattr(arg, 'text') else str(arg)
        return f"sa.text({repr(text_val)})"
    return repr(arg)


def generate():
    tables = sorted(Base.metadata.tables.items(), key=_sort_key)
    lines = []
    lines.append('"""create all tables from SQLAlchemy models')
    lines.append("")
    lines.append("Revision ID: create_all_tables")
    lines.append("Revises: 8d8b122b9742")
    lines.append('"""')
    lines.append("from typing import Sequence, Union")
    lines.append("")
    lines.append("import sqlalchemy as sa")
    lines.append("from alembic import op")
    lines.append("from sqlalchemy.dialects import postgresql")
    lines.append("")
    lines.append("revision: str = 'create_all_tables'")
    lines.append("down_revision: Union[str, None] = '8d8b122b9742'")
    lines.append("branch_labels: Union[str, Sequence[str], None] = None")
    lines.append("depends_on: Union[str, Sequence[str], None] = None")
    lines.append("")
    lines.append("")
    lines.append("def upgrade() -> None:")
    lines.append('    """Create all tables."""')
    lines.append("")

    for name, table in tables:
        lines.append(f"    op.create_table('{name}',")
        for col in table.columns:
            col_str = f"        sa.Column('{col.name}', {_col_type(col)}"
            pos_parts = []  # positional args (must come before keyword args)
            kw_parts = []   # keyword args
            kw = _col_kw(col)

            # ForeignKey is a positional arg
            if "fk" in kw:
                pos_parts.append(kw["fk"])

            if "primary_key" in kw:
                kw_parts.append("primary_key=True")
            if not col.nullable:
                kw_parts.append("nullable=False")
            if "unique" in kw:
                kw_parts.append("unique=True")
            if "comment" in kw:
                kw_parts.append(f"comment={kw['comment']}")

            sd = _server_default(col)
            if sd:
                kw_parts.append(f"server_default={sd}")

            all_parts = pos_parts + kw_parts
            if all_parts:
                col_str += ", " + ", ".join(all_parts)
            col_str += "),"
            lines.append(col_str)

        # CheckConstraints
        for c in table.constraints:
            if isinstance(c, sa.CheckConstraint):
                sql_text = str(c.sqltext).replace("'", "\\'")
                lines.append(f"        sa.CheckConstraint('{sql_text}', name='{c.name}'),")

        # UniqueConstraints
        for c in table.constraints:
            if isinstance(c, sa.UniqueConstraint):
                col_list = ", ".join(repr(k) for k in c.columns.keys())
                lines.append(f"        sa.UniqueConstraint({col_list}, name='{c.name}'),")

        lines.append("    )")
        lines.append("")

    lines.append("")
    lines.append("def downgrade() -> None:")
    lines.append('    """Drop all tables."""')
    for name in reversed([n for n, _ in sorted(tables, key=_sort_key)]):
        lines.append(f"    op.drop_table('{name}')")

    return "\n".join(lines)


if __name__ == "__main__":
    content = generate()

    # Write to versions dir
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "backend", "db", "migrations", "versions",
    )
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "20260626_create_all_tables.py")
    with open(out_path, "w") as f:
        f.write(content)
    print(f"Wrote {out_path}")
    print(f"Total lines: {len(content.splitlines())}")
