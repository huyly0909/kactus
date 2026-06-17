"""add portfolio, items, supported assets, crawl runs

Revision ID: a1b2c3d4e5f6
Revises: 69045d3a1609
Create Date: 2026-06-17 00:00:00.000000

"""

from typing import Sequence, Union

import kactus_common.database.oltp.types
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "69045d3a1609"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "portfolios",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", mysql.BIGINT(unsigned=True), nullable=False),
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
        op.f("ix_portfolios_owner_id"), "portfolios", ["owner_id"], unique=False
    )

    op.create_table(
        "portfolio_items",
        sa.Column("portfolio_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("asset_type", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
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
        sa.UniqueConstraint(
            "portfolio_id", "asset_type", "code", name="uq_portfolio_item"
        ),
    )
    op.create_index(
        op.f("ix_portfolio_items_portfolio_id"),
        "portfolio_items",
        ["portfolio_id"],
        unique=False,
    )

    op.create_table(
        "supported_assets",
        sa.Column("asset_type", sa.String(length=16), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("is_crawlable", sa.Boolean(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column(
            "synced_at",
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
        sa.UniqueConstraint("asset_type", "code", name="uq_supported_asset"),
    )

    op.create_table(
        "crawl_runs",
        sa.Column("asset_type", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("portfolio_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("rows_written", sa.Integer(), nullable=False),
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
        op.f("ix_crawl_runs_asset_type"), "crawl_runs", ["asset_type"], unique=False
    )
    op.create_index(op.f("ix_crawl_runs_kind"), "crawl_runs", ["kind"], unique=False)
    op.create_index(
        op.f("ix_crawl_runs_status"), "crawl_runs", ["status"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_crawl_runs_status"), table_name="crawl_runs")
    op.drop_index(op.f("ix_crawl_runs_kind"), table_name="crawl_runs")
    op.drop_index(op.f("ix_crawl_runs_asset_type"), table_name="crawl_runs")
    op.drop_table("crawl_runs")
    op.drop_table("supported_assets")
    op.drop_index(
        op.f("ix_portfolio_items_portfolio_id"), table_name="portfolio_items"
    )
    op.drop_table("portfolio_items")
    op.drop_index(op.f("ix_portfolios_owner_id"), table_name="portfolios")
    op.drop_table("portfolios")
