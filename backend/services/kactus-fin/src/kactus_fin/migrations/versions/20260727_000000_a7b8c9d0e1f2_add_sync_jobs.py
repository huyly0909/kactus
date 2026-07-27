"""add sync_jobs queue

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-27 00:00:00.000000

The shared sync-job queue: one durable, FIFO row per queued DuckDB write (gold
backfill / sync-now to start; stock later). kactus-fin enqueues PENDING rows;
the single kactus-data-server dispatcher claims / progresses / finishes them.

The partial unique index ``uq_sync_job_active_dedup`` enforces *one live job per
dedup_key* (PENDING or RUNNING) at the DB — the backstop behind the app-level
enqueue check and the "disable if queued" UI. A finished job frees the key.

"""

from typing import Sequence, Union

import kactus_common.database.oltp.types
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sync_jobs",
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("dedup_key", sa.String(length=128), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column("progress_done", sa.Integer(), nullable=False),
        sa.Column("cursor", sa.String(length=64), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column(
            "started_at",
            kactus_common.database.oltp.types.DateTimeTzAware(),
            nullable=True,
        ),
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
        op.f("ix_sync_jobs_dedup_key"), "sync_jobs", ["dedup_key"], unique=False
    )
    op.create_index(
        op.f("ix_sync_jobs_job_type"), "sync_jobs", ["job_type"], unique=False
    )
    op.create_index(op.f("ix_sync_jobs_status"), "sync_jobs", ["status"], unique=False)
    # One live job per dedup_key (PENDING/RUNNING); a finished job frees the key.
    op.create_index(
        "uq_sync_job_active_dedup",
        "sync_jobs",
        ["dedup_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_sync_job_active_dedup", table_name="sync_jobs")
    op.drop_index(op.f("ix_sync_jobs_status"), table_name="sync_jobs")
    op.drop_index(op.f("ix_sync_jobs_job_type"), table_name="sync_jobs")
    op.drop_index(op.f("ix_sync_jobs_dedup_key"), table_name="sync_jobs")
    op.drop_table("sync_jobs")
