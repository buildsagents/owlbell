"""analytics_daily_rollups table

Revision ID: analytics_rollups
Revises: tenant_integrations
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "analytics_rollups"
down_revision: Union[str, None] = "tenant_integrations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_daily_rollups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rollup_date", sa.Date(), nullable=False),
        sa.Column("total_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("answered_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missed_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_handled_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_wait_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("wait_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rolled_up_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "rollup_date", name="uq_analytics_daily_tenant_date"),
    )
    op.create_index(
        "ix_analytics_daily_rollups_tenant_date",
        "analytics_daily_rollups",
        ["tenant_id", "rollup_date"],
    )
    op.create_index(
        "ix_analytics_daily_rollups_rollup_date",
        "analytics_daily_rollups",
        ["rollup_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_analytics_daily_rollups_rollup_date", table_name="analytics_daily_rollups")
    op.drop_index("ix_analytics_daily_rollups_tenant_date", table_name="analytics_daily_rollups")
    op.drop_table("analytics_daily_rollups")