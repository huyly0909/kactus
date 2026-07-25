"""kactus-fin portfolio API schemas — the presentation layer only.

CRUD/catalog schemas, the crawl-control schemas and the generic
``MarketRowSchema`` are reused from :mod:`kactus_common.portfolio.schema`
because the data plane serves them too. What is left here is the shaping
kactus-fin does purely for its own UI: folding stock and gold rows into one
quote row, and the news projection.
"""

from __future__ import annotations

import datetime

from kactus_common.portfolio.const import AssetType
from kactus_common.schemas import BaseSchema, FancyDecimal, FancyFloat


class MarketQuoteSchema(BaseSchema):
    """Unified latest-quote row (covers stock match price + gold buy/sell)."""

    asset_type: AssetType
    code: str
    match_price: FancyDecimal | None = None
    ref_price: FancyDecimal | None = None
    ceiling: FancyDecimal | None = None
    floor: FancyDecimal | None = None
    buy_price: FancyDecimal | None = None
    sell_price: FancyDecimal | None = None
    #: Price unit for gold rows (`VND/luong` vs `USD/oz`); None for stocks.
    unit: str | None = None
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
