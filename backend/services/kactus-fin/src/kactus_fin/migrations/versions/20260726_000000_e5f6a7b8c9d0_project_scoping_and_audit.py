"""project scoping (project_id on user-owned tables) + audit_logs

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-26 00:00:00.000000

Adds a nullable, indexed ``project_id`` to every user-owned table so records can
be scoped to the selected project, and creates the append-only ``audit_logs``
table. ``project_id`` is nullable on purpose: background writers and superuser /
no-project requests insert unscoped rows, and the backfill CLI
(``fin project backfill-personal-projects``) fills existing rows afterwards.

"""

from typing import Sequence, Union

import kactus_common.database.oltp.types
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SCOPED_TABLES = (
    "portfolios",
    "portfolio_items",
    "notification_channels",
    "notification_logs",
    "action_tokens",
    "crawl_runs",
)


def upgrade() -> None:
    """Upgrade schema."""
    for table in _SCOPED_TABLES:
        op.add_column(
            table,
            sa.Column(
                "project_id",
                mysql.BIGINT(unsigned=True),
                nullable=True,
                comment="owning project id",
            ),
        )
        op.create_index(
            op.f(f"ix_{table}_project_id"), table, ["project_id"], unique=False
        )

    op.create_table(
        "audit_logs",
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("project_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=True),
        sa.Column("resource_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
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
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"])
    op.create_index(op.f("ix_audit_logs_project_id"), "audit_logs", ["project_id"])
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"])
    op.create_index(
        op.f("ix_audit_logs_resource_type"), "audit_logs", ["resource_type"]
    )
    op.create_index(op.f("ix_audit_logs_resource_id"), "audit_logs", ["resource_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_audit_logs_resource_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_resource_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_project_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_user_id"), table_name="audit_logs")
    op.drop_table("audit_logs")

    for table in _SCOPED_TABLES:
        op.drop_index(op.f(f"ix_{table}_project_id"), table_name=table)
        op.drop_column(table, "project_id")
