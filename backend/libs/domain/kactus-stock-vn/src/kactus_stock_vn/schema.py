"""Stock API schemas — read models over the OLAP (DuckDB) stock tables.

Every row also carries its ``source`` + crawl/sync timestamp so the UI can show
how stale a figure is; the ETL is scheduled, not live.

Shared: the data plane builds these from DuckDB and serves them over
``/internal/market/*``; the control plane parses the same classes back out of
that response and re-serves them on ``/api/market/*``. One definition, so a
field added on one side cannot be silently dropped by the other.
"""

from __future__ import annotations

from kactus_common.schemas import (
    AwareUTCDatetime,
    BaseSchema,
    FancyDecimal,
    FancyFloat,
    FancyInt,
    OpaqueDict,
)

from .const import ReportPeriod, ReportType


class StockListingSchema(BaseSchema):
    """A listed symbol from the exchange catalogue."""

    symbol: str
    organ_name: str | None = None
    source: str | None = None
    synced_at: AwareUTCDatetime | None = None


class StockQuoteSchema(BaseSchema):
    """Latest price-board snapshot for one symbol."""

    symbol: str
    match_price: FancyDecimal | None = None
    ref_price: FancyDecimal | None = None
    ceiling: FancyDecimal | None = None
    floor: FancyDecimal | None = None
    accumulated_volume: FancyFloat | None = None
    change: FancyDecimal | None = None
    change_pct: FancyFloat | None = None
    source: str | None = None
    crawled_at: AwareUTCDatetime | None = None


class CompanySchema(BaseSchema):
    """Company profile behind a symbol."""

    symbol: str
    company_name: str | None = None
    short_name: str | None = None
    industry: str | None = None
    exchange: str | None = None
    market_cap: FancyDecimal | None = None
    outstanding_shares: FancyFloat | None = None
    source: str | None = None
    synced_at: AwareUTCDatetime | None = None


class StockDetailSchema(BaseSchema):
    """Symbol overview — catalogue entry + company profile + latest quote."""

    symbol: str
    organ_name: str | None = None
    company: CompanySchema | None = None
    quote: StockQuoteSchema | None = None


class OHLCVSchema(BaseSchema):
    """One candle.

    ``event_dt`` is the candle's canonical UTC instant (tz-aware, ``+00:00``),
    derived from the native Vietnam-local candle time at ingest. The client
    localises it to the user's timezone; NULL only for rows not yet backfilled.
    """

    symbol: str
    event_dt: AwareUTCDatetime | None = None
    interval: str
    open: FancyDecimal | None = None
    high: FancyDecimal | None = None
    low: FancyDecimal | None = None
    close: FancyDecimal | None = None
    volume: FancyFloat | None = None
    source: str | None = None


class StockNewsSchema(BaseSchema):
    """A news item attached to a symbol."""

    symbol: str
    news_id: str | None = None
    title: str | None = None
    published_at: str | None = None
    url: str | None = None
    source: str | None = None


class FinanceReportSchema(BaseSchema):
    """One financial-report row.

    ``data`` is the full source row (opaque — vnstock's columns differ per
    report type and data source), kept verbatim so the UI can render whatever
    the crawl captured.
    """

    symbol: str
    report_type: ReportType
    period: ReportPeriod
    year: FancyInt
    quarter: FancyInt | None = None
    data: OpaqueDict = {}
    source: str | None = None
    synced_at: AwareUTCDatetime | None = None
