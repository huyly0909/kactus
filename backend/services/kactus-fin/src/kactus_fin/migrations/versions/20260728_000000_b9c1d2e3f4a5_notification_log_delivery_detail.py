"""notification log delivery detail

Adds the columns that make a send-history row explain itself: what was sent
(``body``), which conversations received it (``targets`` + the delivered/total
counts) and what failed on each try (``attempt_errors``). Before this, a Zalo
fan-out to five conversations logged one row with a title and an attempt count,
so a partial failure was indistinguishable from a clean success.

All columns are nullable — ``notification_logs`` is append-only with no FKs and
no unique constraints, so existing rows simply carry NULLs.

Revision ID: b9c1d2e3f4a5
Revises: f8375746a268
Create Date: 2026-07-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "f8375746a268"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "notification_logs",
        sa.Column(
            "body",
            sa.Text(),
            nullable=True,
            comment="Event body as sent — the full content behind the title",
        ),
    )
    op.add_column(
        "notification_logs",
        sa.Column(
            "targets",
            sa.JSON(),
            nullable=True,
            comment="[{thread_id, thread_type, name, ok, error}] per conversation",
        ),
    )
    op.add_column(
        "notification_logs",
        sa.Column(
            "attempt_errors",
            sa.JSON(),
            nullable=True,
            comment="[{attempt, error, at}] — one entry per failed transport attempt",
        ),
    )
    op.add_column(
        "notification_logs",
        sa.Column(
            "delivered_count",
            sa.Integer(),
            nullable=True,
            comment="Conversations that received the message",
        ),
    )
    op.add_column(
        "notification_logs",
        sa.Column(
            "target_count",
            sa.Integer(),
            nullable=True,
            comment="Conversations attempted",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("notification_logs", "target_count")
    op.drop_column("notification_logs", "delivered_count")
    op.drop_column("notification_logs", "attempt_errors")
    op.drop_column("notification_logs", "body")
    op.drop_column("notification_logs", "targets")
