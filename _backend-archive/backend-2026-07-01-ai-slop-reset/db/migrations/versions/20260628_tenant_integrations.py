"""tenant_integrations, stripe_webhook_events, calls.retell_call_id

Revision ID: tenant_integrations
Revises: onboarding_intakes
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "tenant_integrations"
down_revision: Union[str, None] = "onboarding_intakes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("voice_provider", sa.String(20), nullable=False, server_default="retell"),
        sa.Column("retell_agent_id", sa.String(128), nullable=True),
        sa.Column("retell_llm_id", sa.String(128), nullable=True),
        sa.Column("retell_kb_id", sa.String(128), nullable=True),
        sa.Column("retell_phone_number", sa.String(30), nullable=True),
        sa.Column("stripe_customer_id", sa.String(128), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(128), nullable=True),
        sa.Column("stripe_email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tenant_integrations_tenant_id", "tenant_integrations", ["tenant_id"])
    op.create_index("ix_tenant_integrations_retell_agent_id", "tenant_integrations", ["retell_agent_id"], unique=True)
    op.create_index("ix_tenant_integrations_stripe_customer_id", "tenant_integrations", ["stripe_customer_id"])

    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_id", sa.String(128), nullable=False, unique=True),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("action", sa.String(64), nullable=True),
    )
    op.create_index("ix_stripe_webhook_events_event_id", "stripe_webhook_events", ["event_id"], unique=True)

    op.add_column(
        "calls",
        sa.Column("retell_call_id", sa.String(128), nullable=True, comment="Retell call_id for idempotent ingest"),
    )
    op.create_index(
        "ix_calls_retell_call_id",
        "calls",
        ["retell_call_id"],
        unique=True,
        postgresql_where=sa.text("retell_call_id IS NOT NULL"),
    )

    # Backfill retell_call_id from legacy metadata_json
    op.execute(
        """
        UPDATE calls
        SET retell_call_id = metadata_json->>'retell_call_id'
        WHERE metadata_json->>'retell_call_id' IS NOT NULL
          AND retell_call_id IS NULL
        """
    )

    # Backfill tenant_integrations from tenants.config_json
    op.execute(
        """
        INSERT INTO tenant_integrations (
            id, tenant_id, voice_provider,
            retell_agent_id, retell_llm_id, retell_kb_id, retell_phone_number,
            stripe_customer_id, stripe_subscription_id, stripe_email,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            t.id,
            COALESCE(t.config_json->>'voice_provider', 'retell'),
            NULLIF(t.config_json->>'retell_agent_id', ''),
            NULLIF(t.config_json->>'retell_llm_id', ''),
            NULLIF(t.config_json->>'retell_kb_id', ''),
            COALESCE(
                NULLIF(t.config_json->>'retell_phone_number', ''),
                NULLIF(t.config_json->>'retell_phone', ''),
                NULLIF(t.config_json->>'assigned_phone', '')
            ),
            NULLIF(t.config_json->>'stripe_customer_id', ''),
            NULLIF(t.config_json->>'stripe_subscription_id', ''),
            NULLIF(t.config_json->>'stripe_email', ''),
            NOW(),
            NOW()
        FROM tenants t
        WHERE t.deleted_at IS NULL
        ON CONFLICT (tenant_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_calls_retell_call_id", table_name="calls")
    op.drop_column("calls", "retell_call_id")
    op.drop_index("ix_stripe_webhook_events_event_id", table_name="stripe_webhook_events")
    op.drop_table("stripe_webhook_events")
    op.drop_index("ix_tenant_integrations_stripe_customer_id", table_name="tenant_integrations")
    op.drop_index("ix_tenant_integrations_retell_agent_id", table_name="tenant_integrations")
    op.drop_index("ix_tenant_integrations_tenant_id", table_name="tenant_integrations")
    op.drop_table("tenant_integrations")