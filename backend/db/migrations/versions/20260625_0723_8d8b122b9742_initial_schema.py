"""initial_schema

Revision ID: 8d8b122b9742
Revises: 
Create Date: 2026-06-25 07:23:09.750530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers
revision: str = "8d8b122b9742"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
