"""Market API — read-only access to the crawled gold / stock / finance data.

The rows come from DuckDB, but not from this process: the data plane owns that
file and serves it over ``/internal/market/*``. Reads are session-authenticated
but not project-scoped: market data is public reference data, not user-owned.
"""

from __future__ import annotations

import datetime

from fastapi import Query
from kactus_common.exceptions import NotFoundError
from kactus_common.market.const import (
    DEFAULT_FINANCE_LIMIT,
    DEFAULT_LIST_LIMIT,
    DEFAULT_NEWS_LIMIT,
    DEFAULT_OHLCV_LIMIT,
    OHLCVInterval,
    ReportPeriod,
    ReportType,
)
from kactus_common.market.schema import (
    FinanceReportSchema,
    GoldPriceSchema,
    OHLCVSchema,
    StockDetailSchema,
    StockListingSchema,
    StockNewsSchema,
    StockQuoteSchema,
)
from kactus_common.router import KactusAPIRouter
from kactus_fin import data_client

router = KactusAPIRouter(prefix="/api/market", tags=["market"])


# --------------------------------------------------------------------------- #
# Gold
# --------------------------------------------------------------------------- #
@router.get("/gold")
async def list_gold_prices(
    code: list[str] | None = Query(default=None),
) -> list[GoldPriceSchema]:
    """Latest gold quotes (VND per lượng), optionally filtered by code."""
    return await data_client.list_gold(codes=code)


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
