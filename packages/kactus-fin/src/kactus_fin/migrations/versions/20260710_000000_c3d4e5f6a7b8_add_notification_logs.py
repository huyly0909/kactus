"""add notification_logs

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-10 00:00:00.000000

"""

from typing import Sequence, Union

import kactus_common.database.oltp.types
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "notification_logs",
        sa.Column("channel_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("owner_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("channel_type", sa.String(length=16), nullable=False),
        sa.Column("event_title", sa.String(length=255), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "finished_at",
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_logs_channel_id"),
        "notification_logs",
        ["channel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_logs_owner_id"),
        "notification_logs",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_logs_status"),
        "notification_logs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_notification_logs_status"), table_name="notification_logs"
    )
    op.drop_index(
        op.f("ix_notification_logs_owner_id"), table_name="notification_logs"
    )
    op.drop_index(
        op.f("ix_notification_logs_channel_id"), table_name="notification_logs"
    )
    op.drop_table("notification_logs")
