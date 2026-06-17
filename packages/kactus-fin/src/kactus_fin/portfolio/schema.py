"""kactus-fin portfolio API schemas (market reads + admin views).

CRUD/catalog schemas are reused from :mod:`kactus_common.portfolio.schema`; this
module adds the read-side market schemas served from DuckDB and the admin status
views.
"""

from __future__ import annotations

import datetime

from kactus_common.portfolio.const import AssetType
from kactus_common.schemas import BaseSchema, FancyFloat, FancyInt, OpaqueDict


class MarketQuoteSchema(BaseSchema):
    """Unified latest-quote row (covers stock match price + gold buy/sell)."""

    asset_type: AssetType
    code: str
    match_price: FancyFloat | None = None
    ref_price: FancyFloat | None = None
    ceiling: FancyFloat | None = None
    floor: FancyFloat | None = None
    buy_price: FancyFloat | None = None
    sell_price: FancyFloat | None = None
    volume: FancyFloat | None = None
    source: str | None = None
    crawled_at: datetime.datetime | None = None


class MarketNewsSchema(BaseSchema):
    """A news item attached to a symbol."""

    symbol: str
    news_id: str | None = None
    title: str | None = None
    published_at: str | None = None
    url: str | None = None
    source: str | None = None


class MarketRowSchema(BaseSchema):
    """Generic decision-support row (foreign trade / ratios / events).

    Curated identity in ``symbol``; the full source row in ``data`` (opaque,
    shape varies by dataset and vnstock source)."""

    symbol: str | None = None
    data: OpaqueDict = {}


class CrawlJobSchema(BaseSchema):
    """A scheduled crawl job and its next fire time."""

    id: str
    next_run_time: str | None = None


class CrawlStatusSchema(BaseSchema):
    """Admin crawl/scheduler status snapshot."""

    scheduler_running: bool
    vnstock_tier: str | None = None
    jobs: list[CrawlJobSchema] = []


class CrawlTriggerResponse(BaseSchema):
    """Result of a manual crawl trigger."""

    crawl_run_ids: list[FancyInt] = []
    skipped: bool = False
    message: str = "ok"
