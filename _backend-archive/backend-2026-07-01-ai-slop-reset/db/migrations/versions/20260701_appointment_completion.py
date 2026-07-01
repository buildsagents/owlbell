"""appointment completed_at + review_requested_at

Adds two nullable timestamps to ``appointments`` supporting the post-job
review-request automation (owlbell.txt #5). Both default NULL, so existing
completed rows are not retroactively swept into review requests.

Revision ID: appointment_completion
Revises: analytics_rollups
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "appointment_completion"
down_revision: Union[str, None] = "analytics_rollups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "appointments", sa.Column("review_requested_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("appointments", "review_requested_at")
    op.drop_column("appointments", "completed_at")
