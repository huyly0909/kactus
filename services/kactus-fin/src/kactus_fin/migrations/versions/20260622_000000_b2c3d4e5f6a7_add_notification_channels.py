"""add notification_channels

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-22 00:00:00.000000

"""

from typing import Sequence, Union

import kactus_common.database.oltp.types
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notification_channels",
        sa.Column("owner_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("channel_type", sa.String(length=16), nullable=False),
        # Fernet-encrypted JSON config (bot token / webhook url never plaintext).
        sa.Column(
            "config",
            kactus_common.database.oltp.types.EncryptedJSON(),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "last_used_at",
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
        sa.Column(
            "deleted_timestamp",
            mysql.BIGINT(unsigned=True),
            nullable=True,
            comment="the timestamp when delete, 0 means not deleted",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_channels_owner_id"),
        "notification_channels",
        ["owner_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_notification_channels_owner_id"),
        table_name="notification_channels",
    )
    op.drop_table("notification_channels")
