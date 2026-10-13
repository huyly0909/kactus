"""Portfolio domain ORM models (asset-class agnostic).

A watchlist item is identified by ``(asset_type, code)`` so STOCK / GOLD / COIN
share one schema — a new asset class is a new provider, not a migration.

OLTP (this module) stores *user intent* (which instruments a user watches and
what we are allowed to crawl).  Market *facts* live in DuckDB (OLAP), keyed by
``code`` and dispatched per asset-type provider in ``kactus-data``.
"""

from __future__ import annotations

import datetime

from kactus_common.database.oltp.models import (
    AuditMixin,
    Base,
    LogicalDeleteMixin,
    ModelMixin,
    ProjectScopedMixin,
)
from kactus_common.database.oltp.types import UnsignedBigInt
from sqlalchemy import JSON, Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .const import AssetType, CrawlStatus, CrawlTrigger


class Portfolio(Base, ModelMixin, AuditMixin, LogicalDeleteMixin, ProjectScopedMixin):
    """A project-scoped, user-owned watchlist of financial instruments.

    ``owner_id`` records the creator (audit); access is governed by the owning
    ``project_id`` + the member's role (see ``ProjectScopedMixin``).
    """

    __tablename__ = "portfolios"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    owner_id: Mapped[UnsignedBigInt] = mapped_column(index=True)


class PortfolioItem(Base, ModelMixin, ProjectScopedMixin):
    """Membership of an instrument in a portfolio (watchlist; no qty/cost).

    Carries its own ``project_id`` (denormalized from the parent portfolio) so
    direct item selects are project-scoped too; portfolios never move between
    projects, so it stays consistent.
    """

    __tablename__ = "portfolio_items"

    portfolio_id: Mapped[UnsignedBigInt] = mapped_column(index=True)
    asset_type: Mapped[str] = mapped_column(String(16), default=AssetType.STOCK)
    code: Mapped[str] = mapped_column(String(32))

    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "asset_type", "code", name="uq_portfolio_item"
        ),
    )


class SupportedAsset(Base, ModelMixin):
    """Crawlable instrument catalog — the universe a user can add & we crawl.

    Populated by per-asset-type catalog syncs (e.g. ``Listing.all_symbols()``
    for stock, a small seeded set for gold).  ``tags`` carries index membership
    (``["VN30", "VN100"]``); ``meta_json`` holds type-specific extras (exchange,
    organ name, …).
    """

    __tablename__ = "supported_assets"

    asset_type: Mapped[str] = mapped_column(String(16), default=AssetType.STOCK)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str | None] = mapped_column(String(255), default=None)
    is_crawlable: Mapped[bool] = mapped_column(Boolean, default=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    meta_json: Mapped[dict | None] = mapped_column(JSON, default=dict)
    synced_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

    __table_args__ = (
        UniqueConstraint("asset_type", "code", name="uq_supported_asset"),
    )


class CrawlRun(Base, ModelMixin):
    """Audit record for one crawl execution (cron or manual refresh)."""

    __tablename__ = "crawl_runs"

    asset_type: Mapped[str] = mapped_column(String(16), index=True)
    # quotes | news | foreign_trade | ratios | ohlcv | events | catalog
    kind: Mapped[str] = mapped_column(String(32), index=True)
    trigger: Mapped[str] = mapped_column(String(16), default=CrawlTrigger.CRON)
    portfolio_id: Mapped[UnsignedBigInt | None] = mapped_column(default=None)
    # Plain column (NOT ProjectScopedMixin): cron writes this with no request
    # context, so it is set from the parent portfolio and filtered explicitly.
    project_id: Mapped[UnsignedBigInt | None] = mapped_column(index=True, default=None)
    status: Mapped[str] = mapped_column(
        String(16), default=CrawlStatus.RUNNING, index=True
    )
    rows_written: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

    @property
    def started_at(self) -> datetime.datetime | None:
        """Crawl start time — aliases ``create_time`` for API readability."""
        return self.create_time
