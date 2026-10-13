"""user UI preferences (language + timezone on users)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-26 01:00:00.000000

Adds two nullable, user-scoped preference columns to ``users`` so a user's UI
language and timezone follow their account across devices. Nullable on purpose:
existing rows have no preference set, and the frontend falls back to its own
defaults (``vi`` / ``Asia/Ho_Chi_Minh``) when the column is NULL.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("language", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "timezone")
    op.drop_column("users", "language")
