"""Market API — read-only access to the crawled gold / stock / finance data.

The rows come from DuckDB, but not from this process: the data plane owns that
file and serves it over ``/internal/market/*``. Reads are session-authenticated
but not project-scoped: market data is public reference data, not user-owned.
"""

from __future__ import annotations

import datetime

from fastapi import Query
from kactus_common.exceptions import NotFoundError
from kactus_common.router import KactusAPIRouter
from kactus_common.settings.service import GlobalSettingsService
from kactus_fin import data_client
from kactus_fin.dependencies import provide_session
from kactus_gold.const import DEFAULT_GOLD_HISTORY_LIMIT, GOLD_AVAILABILITY_SCHEDULE
from kactus_gold.schedule import gold_schedule_entity_id
from kactus_gold.schema import (
    GoldHistoryCodeSchema,
    GoldHistoryPointSchema,
    GoldPriceSchema,
    GoldScheduleSchema,
)
from kactus_stock_vn.const import (
    DEFAULT_DAILY_LIMIT,
    DEFAULT_EVENTS_LIMIT,
    DEFAULT_FINANCE_LIMIT,
    DEFAULT_LIST_LIMIT,
    DEFAULT_NEWS_LIMIT,
    DEFAULT_OHLCV_LIMIT,
    OHLCVInterval,
    ReportPeriod,
    ReportType,
    TechnicalInterval,
)
from kactus_stock_vn.schema import (
    FinanceReportSchema,
    FundamentalRadarSchema,
    OHLCVSchema,
    StockDailyListSchema,
    StockDetailSchema,
    StockEventSchema,
    StockListingSchema,
    StockNewsSchema,
    StockOverviewSchema,
    StockQuoteSchema,
    TechnicalGaugeSchema,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = KactusAPIRouter(prefix="/api/market", tags=["market"])


# --------------------------------------------------------------------------- #
# Gold
# --------------------------------------------------------------------------- #
@router.get("/gold")
async def list_gold_prices(
    code: list[str] | None = Query(default=None),
) -> list[GoldPriceSchema]:
    """Latest gold quotes, optionally filtered by code.

    One row per ``(code, source)`` — a code may return **several** rows (SJC
    and mihong both quote 999), and units differ per row: domestic is
    VND/lượng, XAU is USD/oz.
    """
    return await data_client.list_gold(codes=code)


# ``code`` is a query param, not a path segment — PNJ series codes carry
# spaces, colons and diacritics ("PNJ:Hà Nội:Vàng 916").
@router.get("/gold/history")
async def list_gold_history(
    code: str,
    source: str | None = None,
    start: datetime.date | None = None,
    end: datetime.date | None = None,
    limit: int = DEFAULT_GOLD_HISTORY_LIMIT,
) -> list[GoldHistoryPointSchema]:
    """Daily points for one gold series, oldest → newest.

    Series identity is ``(source, code)`` — pass ``source`` to chart one
    series, or omit it to get every feed serving the code, interleaved.
    """
    return await data_client.list_gold_history(
        code=code, source=source, start=start, end=end, limit=limit
    )


@router.get("/gold/history/codes")
async def list_gold_history_codes() -> list[GoldHistoryCodeSchema]:
    """Catalogue of stored gold series (for the history chart's picker)."""
    return await data_client.list_gold_history_codes()


@router.get("/gold/schedule")
@provide_session
async def get_gold_schedule(
    source: str,
    code: str,
    session: AsyncSession,
) -> GoldScheduleSchema:
    """Data-availability schedule for one gold series (drives gap / stale chips).

    OLTP config (``global_settings``), not DuckDB — read directly, not via the
    data plane. Returns the series' expected weekdays + holidays + market timezone.
    """
    cfg = await GlobalSettingsService.load(
        session,
        entity_type=GOLD_AVAILABILITY_SCHEDULE,
        entity_id=gold_schedule_entity_id(source, code),
    )
    return GoldScheduleSchema(source=source, code=code, **cfg.model_dump())


# --------------------------------------------------------------------------- #
# Stocks — static segments first so they never match "/{symbol}".
# --------------------------------------------------------------------------- #
@router.get("/stocks")
async def search_stocks(
    q: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[StockListingSchema]:
    """Search the listed-symbol catalogue by ticker or company name."""
    return await data_client.search_stocks(q=q, limit=limit)


@router.get("/stocks/quotes")
async def list_stock_quotes(
    symbol: list[str] | None = Query(default=None),
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[StockQuoteSchema]:
    """Latest price-board snapshots for the given symbols (or the whole board)."""
    return await data_client.list_quotes(symbols=symbol, limit=limit)


@router.get("/stocks/{symbol}")
async def get_stock(symbol: str) -> StockDetailSchema:
    """Symbol overview — catalogue entry, company profile and latest quote."""
    detail = await data_client.get_stock(symbol)
    if detail is None:
        raise NotFoundError(f"No market data for symbol '{symbol.upper()}'")
    return detail


@router.get("/stocks/{symbol}/ohlcv")
async def list_ohlcv(
    symbol: str,
    interval: OHLCVInterval = OHLCVInterval.D1,
    start: datetime.date | None = None,
    end: datetime.date | None = None,
    limit: int = DEFAULT_OHLCV_LIMIT,
) -> list[OHLCVSchema]:
    """Candles for a symbol, oldest → newest."""
    return await data_client.list_ohlcv(
        symbol, interval=str(interval), start=start, end=end, limit=limit
    )


@router.get("/stocks/{symbol}/news")
async def list_stock_news(
    symbol: str,
    limit: int = DEFAULT_NEWS_LIMIT,
) -> list[StockNewsSchema]:
    """Recent news for a symbol."""
    return await data_client.list_news(symbol, limit=limit)


# --------------------------------------------------------------------------- #
# Finance
# --------------------------------------------------------------------------- #
@router.get("/stocks/{symbol}/finance")
async def list_finance_reports(
    symbol: str,
    report_type: ReportType = ReportType.INCOME_STATEMENT,
    period: ReportPeriod | None = None,
    limit: int = DEFAULT_FINANCE_LIMIT,
) -> list[FinanceReportSchema]:
    """Financial reports for a symbol, newest period first."""
    return await data_client.list_finance(
        symbol,
        report_type=str(report_type),
        period=str(period) if period is not None else None,
        limit=limit,
    )


# --------------------------------------------------------------------------- #
# Stock detail — the panels behind the symbol page.
# --------------------------------------------------------------------------- #
@router.get("/stocks/{symbol}/overview")
async def get_stock_overview(symbol: str) -> StockOverviewSchema:
    """Header + sidebar for the detail page.

    One endpoint rather than four: the sidebar mixes the price board, company
    profile, candle history and statements, and splitting it would make the
    page's slowest read its total latency.
    """
    overview = await data_client.get_stock_overview(symbol)
    if overview is None:
        raise NotFoundError(f"No market data for symbol '{symbol.upper()}'")
    return overview


@router.get("/stocks/{symbol}/events")
async def list_stock_events(
    symbol: str,
    limit: int = DEFAULT_EVENTS_LIMIT,
) -> list[StockEventSchema]:
    """Corporate events — dividends, record dates, insider deals."""
    return await data_client.list_events(symbol, limit=limit)


@router.get("/stocks/{symbol}/daily")
async def list_stock_daily(
    symbol: str,
    limit: int = DEFAULT_DAILY_LIMIT,
) -> StockDailyListSchema:
    """Per-session trading table with foreign flow, newest session first.

    Foreign-flow columns are NULL before ``snapshot_from``: they are captured
    from the live board each session and cannot be backfilled.
    """
    return await data_client.list_daily(symbol, limit=limit)


@router.get("/stocks/{symbol}/technical")
async def get_stock_technical(
    symbol: str,
    interval: TechnicalInterval = TechnicalInterval.D1,
) -> TechnicalGaugeSchema:
    """Indicator consensus computed from stored candles (derived, not sourced)."""
    return await data_client.get_technical(symbol, interval=str(interval))


@router.get("/stocks/{symbol}/fundamental")
async def get_stock_fundamental(symbol: str) -> FundamentalRadarSchema:
    """Five-axis fundamental score, percentile-ranked against comparable peers."""
    return await data_client.get_fundamental(symbol)
