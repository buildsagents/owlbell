"""add onboarding_intakes table

Revision ID: onboarding_intakes
Revises: create_all_tables
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "onboarding_intakes"
down_revision: Union[str, None] = "create_all_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "onboarding_intakes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("business_name", sa.String(255), nullable=False),
        sa.Column("stripe_session_id", sa.String(255), nullable=True),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_onboarding_intakes_tenant_id", "onboarding_intakes", ["tenant_id"])
    op.create_index("ix_onboarding_intakes_email", "onboarding_intakes", ["email"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_intakes_email", table_name="onboarding_intakes")
    op.drop_index("ix_onboarding_intakes_tenant_id", table_name="onboarding_intakes")
    op.drop_table("onboarding_intakes")