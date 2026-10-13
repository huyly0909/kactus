"""sync_jobs create_time index

The scheduler Queue tab orders and pages the whole ``sync_jobs`` table on
``create_time`` (newest first). The table only ever grows and carried indexes
on ``job_type`` / ``dedup_key`` / ``status`` only, so every page was a full
sort of the table.

Revision ID: c1d2e3f4a5b6
Revises: b9c1d2e3f4a5
Create Date: 2026-07-28 01:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "b9c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("ix_sync_jobs_create_time", "sync_jobs", ["create_time"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_sync_jobs_create_time", table_name="sync_jobs")
