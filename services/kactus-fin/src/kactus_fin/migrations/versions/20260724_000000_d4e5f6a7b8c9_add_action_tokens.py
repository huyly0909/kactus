"""add action_tokens

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-24 00:00:00.000000

"""

from typing import Sequence, Union

import kactus_common.database.oltp.types
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "action_tokens",
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column(
            "expires_at",
            kactus_common.database.oltp.types.DateTimeTzAware(),
            nullable=False,
        ),
        sa.Column(
            "consumed_at",
            kactus_common.database.oltp.types.DateTimeTzAware(),
            nullable=True,
        ),
        sa.Column(
            "id", mysql.BIGINT(unsigned=True), autoincrement=False, nullable=False
        ),
        sa.Column(
            "create_time",
            kactus_common.database.oltp.types.DateTimeTzAware(),
            nullable=True,
        ),
        sa.Column(
            "update_time",
            kactus_common.database.oltp.types.DateTimeTzAware(),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            mysql.BIGINT(unsigned=True),
            nullable=True,
            comment="create user id",
        ),
        sa.Column(
            "updated_by",
            mysql.BIGINT(unsigned=True),
            nullable=True,
            comment="update user id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_action_tokens_user_id"), "action_tokens", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_action_tokens_action"), "action_tokens", ["action"], unique=False
    )
    # Indexed for the housekeeping sweep that prunes dead tokens; nothing in the
    # request path filters on it (a token is always reached by primary key).
    op.create_index(
        op.f("ix_action_tokens_expires_at"),
        "action_tokens",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_action_tokens_expires_at"), table_name="action_tokens")
    op.drop_index(op.f("ix_action_tokens_action"), table_name="action_tokens")
    op.drop_index(op.f("ix_action_tokens_user_id"), table_name="action_tokens")
    op.drop_table("action_tokens")
