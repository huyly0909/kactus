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

from .const import (
    PeerBasis,
    ReportPeriod,
    ReportType,
    SignalGroup,
    TechnicalConsensus,
    TechnicalInterval,
    TechnicalSignal,
)


class StockListingSchema(BaseSchema):
    """A listed symbol from the exchange catalogue."""

    symbol: str
    organ_name: str | None = None
    source: str | None = None
    synced_at: AwareUTCDatetime | None = None


class StockQuoteSchema(BaseSchema):
    """Latest price-board snapshot for one symbol.

    The fields below ``change_pct`` are session detail pulled from the same
    board row's raw payload. They are optional because only the richer sources
    publish them, and a board row without them is still a valid quote.
    """

    symbol: str
    match_price: FancyDecimal | None = None
    ref_price: FancyDecimal | None = None
    ceiling: FancyDecimal | None = None
    floor: FancyDecimal | None = None
    accumulated_volume: FancyFloat | None = None
    change: FancyDecimal | None = None
    change_pct: FancyFloat | None = None
    open: FancyDecimal | None = None
    high: FancyDecimal | None = None
    low: FancyDecimal | None = None
    # Traded value for the session, in absolute VND — the board publishes it in
    # millions and it is converted on read so every money field shares a unit.
    value_vnd: FancyDecimal | None = None
    # Resting volume summed over every published depth level, not just level 1
    # (those differ by an order of magnitude).
    remain_bid: FancyFloat | None = None
    remain_ask: FancyFloat | None = None
    foreign_buy_volume: FancyFloat | None = None
    foreign_sell_volume: FancyFloat | None = None
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


class StockEventSchema(BaseSchema):
    """A corporate event — dividend, AGM, insider deal, record date."""

    symbol: str
    event_id: str | None = None
    title: str | None = None
    event_date: str | None = None
    category: str | None = None
    event_name: str | None = None
    exright_date: str | None = None
    record_date: str | None = None
    value_per_share: FancyDecimal | None = None
    source: str | None = None


class StockDailySchema(BaseSchema):
    """One trading session for one symbol.

    Price and volume come from the candle history and go back as far as it
    does. Everything from ``value_vnd`` down comes from the end-of-session
    snapshot and is therefore NULL before snapshots began for this symbol —
    ``StockDailyListSchema.snapshot_from`` says when that was. A NULL here
    means "not captured", never zero.
    """

    symbol: str
    trade_date: str
    open: FancyDecimal | None = None
    high: FancyDecimal | None = None
    low: FancyDecimal | None = None
    close: FancyDecimal | None = None
    change: FancyDecimal | None = None
    change_pct: FancyFloat | None = None
    volume: FancyFloat | None = None
    value_vnd: FancyDecimal | None = None
    remain_bid: FancyFloat | None = None
    remain_ask: FancyFloat | None = None
    avg_buy_size: FancyFloat | None = None
    avg_sell_size: FancyFloat | None = None
    foreign_buy_volume: FancyFloat | None = None
    foreign_sell_volume: FancyFloat | None = None
    foreign_buy_value: FancyDecimal | None = None
    foreign_sell_value: FancyDecimal | None = None
    foreign_net_value: FancyDecimal | None = None


class StockDailyListSchema(BaseSchema):
    """Daily rows plus the provenance the UI needs to caption blank columns."""

    symbol: str
    rows: list[StockDailySchema] = []
    # First session captured. Foreign-flow columns are NULL before this date and
    # can never be backfilled — vnstock serves no historical foreign-flow feed.
    snapshot_from: str | None = None
    # Proprietary-desk (tự doanh) flow has no source on any vnstock provider.
    # Advertised as a capability flag so the client renders "n/a", not "0".
    proprietary_supported: bool = False


class TechnicalSignalSchema(BaseSchema):
    """One indicator's reading and the vote it casts."""

    name: str
    group: SignalGroup
    value: FancyFloat | None = None
    vote: TechnicalSignal


class TechnicalVoteCountSchema(BaseSchema):
    """How the indicators split."""

    buy: FancyInt = 0
    neutral: FancyInt = 0
    sell: FancyInt = 0


class TechnicalGaugeSchema(BaseSchema):
    """Indicator consensus for one symbol at one interval.

    Derived, not fetched: vnstock serves no indicator surface. Indicators
    without enough history are omitted rather than counted neutral, so
    ``counts`` may total fewer than the full indicator set on a short history.
    """

    symbol: str
    interval: TechnicalInterval
    bars: FancyInt
    price: FancyFloat | None = None
    label: TechnicalConsensus
    # Mean vote in [-1, 1]; NULL when no indicator had enough history.
    score: FancyFloat | None = None
    counts: TechnicalVoteCountSchema = TechnicalVoteCountSchema()
    signals: list[TechnicalSignalSchema] = []


class FundamentalMetricSchema(BaseSchema):
    """One ratio's value and where it ranks among peers."""

    metric: str
    value: FancyFloat | None = None
    # 0-1 rank within the peer set, already oriented so higher is always better.
    percentile: FancyFloat
    peer_median: FancyFloat | None = None


class FundamentalAxisSchema(BaseSchema):
    """One radar axis, scored 0-10, plus the metrics behind it."""

    axis: str
    score: FancyFloat | None = None
    # A median peer sits at the 50th percentile on every metric by
    # construction, so the industry ring is 5.0 wherever the axis scored.
    industry: FancyFloat | None = None
    metrics: list[FundamentalMetricSchema] = []


class FundamentalRadarSchema(BaseSchema):
    """Five-axis fundamental score for one symbol, relative to its peers.

    Percentile-based, so a 10 means best-in-cohort rather than good in absolute
    terms. ``as_of`` is the ratio period the score describes — on a restricted
    vnstock tier that can lag the current year by a lot, and presenting it
    undated would turn a stale number into a wrong one.
    """

    symbol: str
    available: bool
    reason: str | None = None
    is_bank: bool = False
    sector: str | None = None
    basis: PeerBasis | None = None
    as_of: str | None = None
    peers: FancyInt = 0
    peer_symbols: list[str] = []
    overall: FancyFloat | None = None
    grade: str | None = None
    axes: list[FundamentalAxisSchema] = []


class TTMSchema(BaseSchema):
    """A trailing-twelve-month (or full fiscal year) roll-up of the statements.

    Two profit lines because sources disagree on which they display:
    ``profit`` is the whole group after tax, ``profit_attributable`` strips
    minority interests and is what per-share figures divide by.
    """

    quarters: FancyInt
    # True when fewer than four quarters were available — the sum is then not a
    # twelve-month figure and must not be labelled as one.
    partial: bool = False
    period_from: str | None = None
    period_to: str | None = None
    year: FancyInt | None = None
    revenue: FancyDecimal | None = None
    profit: FancyDecimal | None = None
    profit_attributable: FancyDecimal | None = None


class StockStatsSchema(BaseSchema):
    """Headline valuation and ownership figures for the detail sidebar.

    The multiples are computed from the current price and the trailing
    statements rather than read from the ratio feed. On a restricted vnstock
    tier that feed can be frozen years in the past, and a P/E from then is not
    a stale number, it is the wrong one. See ``stale_ratios`` on the overview
    for the raw feed values, which are always carried with their own period.
    """

    pe: FancyFloat | None = None
    pb: FancyFloat | None = None
    ps: FancyFloat | None = None
    eps: FancyFloat | None = None
    bvps: FancyFloat | None = None
    roe: FancyFloat | None = None
    equity: FancyDecimal | None = None
    equity_period: str | None = None
    market_cap: FancyDecimal | None = None
    outstanding_shares: FancyFloat | None = None
    free_float_pct: FancyFloat | None = None
    dividend_per_share: FancyFloat | None = None
    dividend_yield: FancyFloat | None = None
    foreign_owned_pct: FancyFloat | None = None
    foreign_room_pct: FancyFloat | None = None
    state_pct: FancyFloat | None = None
    high_52w: FancyDecimal | None = None
    low_52w: FancyDecimal | None = None
    avg_volume_52w: FancyFloat | None = None
    beta: FancyFloat | None = None


class StaleRatiosSchema(BaseSchema):
    """Multiples exactly as the ratio feed reports them, with their period.

    Kept separate from :class:`StockStatsSchema` so a client cannot render feed
    values as current by accident — the period is not optional here.
    """

    period: str | None = None
    pe: FancyFloat | None = None
    pb: FancyFloat | None = None
    ps: FancyFloat | None = None
    roe: FancyFloat | None = None
    roa: FancyFloat | None = None


class AnalystViewSchema(BaseSchema):
    """The data source's own analyst call, where it publishes one.

    There is no forward P/E in the feed; the target price and rating stand in
    for it rather than being derived.
    """

    rating: str | None = None
    target_price: FancyDecimal | None = None
    upside_pct: FancyFloat | None = None
    analyst: str | None = None
    rating_as_of: str | None = None


class StockOverviewSchema(BaseSchema):
    """Everything the detail header and sidebar need, in one read.

    A single endpoint on purpose: the sidebar mixes the price board, company
    profile, candle history and statements, and issuing four round trips to
    render one panel would make the page's slowest read its total latency.
    """

    symbol: str
    organ_name: str | None = None
    short_name: str | None = None
    sector: str | None = None
    exchange: str | None = None
    profile: str | None = None
    listing_date: str | None = None
    quote: StockQuoteSchema | None = None
    stats: StockStatsSchema = StockStatsSchema()
    stale_ratios: StaleRatiosSchema | None = None
    analyst: AnalystViewSchema | None = None
    ttm: TTMSchema | None = None
    fy: TTMSchema | None = None
