"""``/internal/market/*`` — the seven MarketService reads, over HTTP.

A one-to-one mirror of :class:`kactus_data.market.service.MarketService`, on
purpose: kactus-fin's ``/api/market/*`` endpoints keep their shape and swap a
direct call for a client call. Query-parameter names match the public API too,
so the client is a pass-through and there is no translation layer to get wrong.

Nothing here decides anything. Authorization, 404 semantics and error copy stay
in the control plane; this returns rows or an empty list.
"""

from __future__ import annotations

import datetime

from fastapi import Depends, Query
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
from kactus_data.market.service import MarketService
from kactus_data_server.runtime import get_runtime
from kactus_data_server.security import require_service_token

router = KactusAPIRouter(
    prefix="/internal/market",
    tags=["internal-market"],
    dependencies=[Depends(require_service_token)],
)


@router.get("/gold")
async def list_gold_prices(
    code: list[str] | None = Query(default=None),
) -> list[GoldPriceSchema]:
    """Latest gold quotes (VND per lượng), optionally filtered by code."""
    return await MarketService.list_gold(get_runtime().storage, codes=code)


# Static segments first so they never match "/{symbol}".
@router.get("/stocks")
async def search_stocks(
    q: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[StockListingSchema]:
    """Search the listed-symbol catalogue by ticker or company name."""
    return await MarketService.search_stocks(get_runtime().storage, q=q, limit=limit)


@router.get("/stocks/quotes")
async def list_stock_quotes(
    symbol: list[str] | None = Query(default=None),
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[StockQuoteSchema]:
    """Latest price-board snapshots for the given symbols (or the whole board)."""
    return await MarketService.list_quotes(
        get_runtime().storage, symbols=symbol, limit=limit
    )


@router.get("/stocks/{symbol}")
async def get_stock(symbol: str) -> StockDetailSchema | None:
    """Symbol overview, or ``null`` when the symbol is in no source table.

    Returns null rather than 404: whether an unknown symbol is an error is the
    control plane's call, and it owns the message the user reads. A 404 here
    would also be indistinguishable from a mistyped route.
    """
    return await MarketService.get_stock(get_runtime().storage, symbol)


@router.get("/stocks/{symbol}/ohlcv")
async def list_ohlcv(
    symbol: str,
    interval: OHLCVInterval = OHLCVInterval.D1,
    start: datetime.date | None = None,
    end: datetime.date | None = None,
    limit: int = DEFAULT_OHLCV_LIMIT,
) -> list[OHLCVSchema]:
    """Candles for a symbol, oldest → newest."""
    return await MarketService.list_ohlcv(
        get_runtime().storage,
        symbol,
        interval=str(interval),
        start=start,
        end=end,
        limit=limit,
    )


@router.get("/stocks/{symbol}/news")
async def list_stock_news(
    symbol: str,
    limit: int = DEFAULT_NEWS_LIMIT,
) -> list[StockNewsSchema]:
    """Recent news for a symbol."""
    return await MarketService.list_news(get_runtime().storage, symbol, limit=limit)


@router.get("/stocks/{symbol}/finance")
async def list_finance_reports(
    symbol: str,
    report_type: ReportType = ReportType.INCOME_STATEMENT,
    period: ReportPeriod | None = None,
    limit: int = DEFAULT_FINANCE_LIMIT,
) -> list[FinanceReportSchema]:
    """Financial reports for a symbol, newest period first."""
    return await MarketService.list_finance(
        get_runtime().storage,
        symbol,
        report_type=report_type,
        period=period,
        limit=limit,
    )
