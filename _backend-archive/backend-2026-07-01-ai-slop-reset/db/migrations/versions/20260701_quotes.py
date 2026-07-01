"""quotes table

Customer quotes / estimates that the follow-up automation chases while they
sit in ``sent`` (owlbell.txt #4).

Revision ID: quotes
Revises: appointment_completion
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "quotes"
down_revision: Union[str, None] = "appointment_completion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id"),
            nullable=True,
        ),
        sa.Column("customer_number", sa.String(30), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("title", sa.String(255), nullable=False, server_default="Quote"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "SENT", "ACCEPTED", "DECLINED", "EXPIRED", name="quotestatus"
            ),
            nullable=False,
            server_default="SENT",
        ),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("declined_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_followup_at", sa.DateTime(), nullable=True),
        sa.Column("followup_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_quotes_tenant_id", "quotes", ["tenant_id"])
    op.create_index("ix_quotes_status", "quotes", ["status"])


def downgrade() -> None:
    op.drop_index("ix_quotes_status", table_name="quotes")
    op.drop_index("ix_quotes_tenant_id", table_name="quotes")
    op.drop_table("quotes")
    sa.Enum(name="quotestatus").drop(op.get_bind(), checkfirst=True)
