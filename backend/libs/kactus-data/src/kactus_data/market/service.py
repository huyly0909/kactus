"""Market service — read-only queries over the OLAP (DuckDB) tables.

DuckDB access is blocking, so every public method hops to a worker thread via
``asyncio.to_thread``.  Tables are written by the kactus-data ETL; a table that
has never been crawled simply does not exist yet, which is treated as "no data"
rather than an error.  All caller-supplied values are bound as query parameters
— never interpolated.

Only the data plane calls this: DuckDB allows one read-write process OR several
read-only ones, never both across processes, so the service that owns the write
handle is the only one that may read. Everyone else goes through
``/internal/market/*``.
"""

from __future__ import annotations

import asyncio
import datetime
import json

import pandas as pd
from kactus_common.datetimes import to_utc_naive
from kactus_common.market.const import (
    DEFAULT_GOLD_HISTORY_LIMIT,
    GOLD_HISTORY_MAX_LIMIT,
    MAX_LIMIT,
    ReportPeriod,
    ReportType,
)
from kactus_common.market.schema import (
    CompanySchema,
    FinanceReportSchema,
    GoldHistoryCodeSchema,
    GoldHistoryPointSchema,
    GoldPriceSchema,
    OHLCVSchema,
    StockDetailSchema,
    StockListingSchema,
    StockNewsSchema,
    StockQuoteSchema,
)
from kactus_data.market.const import (
    GOLD_BOARD_TABLE,
    GOLD_HISTORY_TABLE,
    STOCK_COMPANY_TABLE,
    STOCK_FINANCE_TABLE,
    STOCK_LISTING_TABLE,
    STOCK_NEWS_TABLE,
    STOCK_OHLCV_TABLE,
    STOCK_PRICE_BOARD_TABLE,
)
from kactus_data.storage.duckdb import DuckDBStorage
from loguru import logger


def _clamp(limit: int, default: int) -> int:
    """Bound a caller-supplied row limit into ``1..MAX_LIMIT``."""
    if limit <= 0:
        return default
    return min(limit, MAX_LIMIT)


def _rows(storage: DuckDBStorage, sql: str, params: list | None = None) -> list[dict]:
    """Run *sql* and return NaN-free row dicts (empty if the table is absent)."""
    try:
        df = storage.query(sql, params)
    except Exception as ex:  # table not created by the ETL yet, or a bad read
        logger.debug("Market query returned no data ({sql}): {ex}", sql=sql, ex=ex)
        return []
    if df is None or df.empty:
        return []
    # NaN/NaT are not JSON-serialisable and mean "missing" here — normalise to None.
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


def _loads(raw: str | None) -> dict:
    """Parse a stored JSON blob, tolerating nulls and malformed rows."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


class MarketService:
    """Read models for the gold / stock / finance datasets."""

    # ------------------------------------------------------------------ gold
    @staticmethod
    async def list_gold(
        storage: DuckDBStorage, *, codes: list[str] | None = None
    ) -> list[GoldPriceSchema]:
        """Latest quote for every gold code (optionally filtered)."""

        def _read() -> list[dict]:
            sql = f"SELECT * FROM {GOLD_BOARD_TABLE}"  # noqa: S608 - fixed table name
            params: list = []
            if codes:
                placeholders = ", ".join("?" for _ in codes)
                sql += f" WHERE code IN ({placeholders})"
                params = list(codes)
            sql += " ORDER BY code"
            return _rows(storage, sql, params or None)

        rows = await asyncio.to_thread(_read)
        out: list[GoldPriceSchema] = []
        for r in rows:
            buy, sell = r.get("buy_price"), r.get("sell_price")
            out.append(
                GoldPriceSchema(
                    code=r["code"],
                    buy_price=buy,
                    sell_price=sell,
                    spread=(
                        (sell - buy) if buy is not None and sell is not None else None
                    ),
                    unit=r.get("unit"),
                    source=r.get("source"),
                    crawled_at=r.get("crawled_at"),
                )
            )
        return out

    @staticmethod
    async def list_gold_history(
        storage: DuckDBStorage,
        *,
        code: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
        limit: int = DEFAULT_GOLD_HISTORY_LIMIT,
    ) -> list[GoldHistoryPointSchema]:
        """Daily points for one gold series, oldest → newest (newest *limit*).

        Gold history has its own cap: the XAU series alone exceeds the global
        ``MAX_LIMIT``, which would silently truncate a full-range request.
        """
        capped = (
            DEFAULT_GOLD_HISTORY_LIMIT
            if limit <= 0
            else min(limit, GOLD_HISTORY_MAX_LIMIT)
        )

        def _read() -> list[dict]:
            sql = f"SELECT * FROM {GOLD_HISTORY_TABLE} WHERE code = ?"  # noqa: S608
            params: list = [code]
            if start is not None:
                sql += " AND date >= ?"
                params.append(start)
            if end is not None:
                sql += " AND date <= ?"
                params.append(end)
            # Newest first so the cap keeps the *recent* window, then re-sorted below.
            sql += f" ORDER BY date DESC LIMIT {capped}"
            return _rows(storage, sql, params)

        rows = await asyncio.to_thread(_read)
        points = [GoldHistoryPointSchema.model_validate(r) for r in rows]
        points.reverse()
        return points

    @staticmethod
    async def list_gold_history_codes(
        storage: DuckDBStorage,
    ) -> list[GoldHistoryCodeSchema]:
        """Catalogue of stored gold series (code, unit, span, point count)."""

        def _read() -> list[dict]:
            sql = (
                "SELECT code, unit, count(*) AS points, "
                "min(date) AS first_date, max(date) AS last_date, "
                "any_value(location) AS location, any_value(gold_type) AS gold_type "
                f"FROM {GOLD_HISTORY_TABLE} "  # noqa: S608
                "GROUP BY code, unit ORDER BY code"
            )
            return _rows(storage, sql)

        rows = await asyncio.to_thread(_read)
        return [GoldHistoryCodeSchema.model_validate(r) for r in rows]

    # ----------------------------------------------------------------- stock
    @staticmethod
    async def search_stocks(
        storage: DuckDBStorage, *, q: str | None = None, limit: int = 50
    ) -> list[StockListingSchema]:
        """Search the listing catalogue by symbol or company name."""
        capped = _clamp(limit, 50)

        def _read() -> list[dict]:
            sql = (
                f"SELECT * FROM {STOCK_LISTING_TABLE}"  # noqa: S608 - fixed table name
            )
            params: list = []
            if q:
                sql += " WHERE symbol ILIKE ? OR organ_name ILIKE ?"
                params = [f"%{q}%", f"%{q}%"]
            sql += f" ORDER BY symbol LIMIT {capped}"
            return _rows(storage, sql, params or None)

        rows = await asyncio.to_thread(_read)
        return [StockListingSchema.model_validate(r) for r in rows]

    @staticmethod
    async def get_stock(
        storage: DuckDBStorage, symbol: str
    ) -> StockDetailSchema | None:
        """Catalogue entry + company profile + latest quote for one symbol.

        Returns ``None`` only when the symbol is absent from *every* source
        table — a symbol that has been listed but never quoted still resolves.
        """
        code = symbol.upper()

        def _read() -> tuple[list[dict], list[dict], list[dict]]:
            listing = _rows(
                storage,
                f"SELECT * FROM {STOCK_LISTING_TABLE} WHERE symbol = ?",  # noqa: S608
                [code],
            )
            company = _rows(
                storage,
                f"SELECT * FROM {STOCK_COMPANY_TABLE} WHERE symbol = ?",  # noqa: S608
                [code],
            )
            quote = _rows(
                storage,
                f"SELECT * FROM {STOCK_PRICE_BOARD_TABLE} WHERE symbol = ?",  # noqa: S608
                [code],
            )
            return listing, company, quote

        listing, company, quote = await asyncio.to_thread(_read)
        if not listing and not company and not quote:
            return None

        return StockDetailSchema(
            symbol=code,
            organ_name=listing[0].get("organ_name") if listing else None,
            company=CompanySchema.model_validate(company[0]) if company else None,
            quote=_to_quote(quote[0]) if quote else None,
        )

    @staticmethod
    async def list_quotes(
        storage: DuckDBStorage, *, symbols: list[str] | None = None, limit: int = 50
    ) -> list[StockQuoteSchema]:
        """Latest price-board snapshots (optionally for specific symbols)."""
        capped = _clamp(limit, 50)

        def _read() -> list[dict]:
            sql = f"SELECT * FROM {STOCK_PRICE_BOARD_TABLE}"  # noqa: S608
            params: list = []
            if symbols:
                placeholders = ", ".join("?" for _ in symbols)
                sql += f" WHERE symbol IN ({placeholders})"
                params = [s.upper() for s in symbols]
            sql += f" ORDER BY symbol LIMIT {capped}"
            return _rows(storage, sql, params or None)

        rows = await asyncio.to_thread(_read)
        return [_to_quote(r) for r in rows]

    @staticmethod
    async def list_ohlcv(
        storage: DuckDBStorage,
        symbol: str,
        *,
        interval: str = "1D",
        start: datetime.date | None = None,
        end: datetime.date | None = None,
        limit: int = 500,
    ) -> list[OHLCVSchema]:
        """Candles for a symbol, oldest → newest (the newest *limit* rows)."""
        capped = _clamp(limit, 500)
        code = symbol.upper()

        def _read() -> list[dict]:
            sql = f"SELECT * FROM {STOCK_OHLCV_TABLE} WHERE symbol = ? AND interval = ?"  # noqa: S608
            params: list = [code, interval]
            # ``event_dt`` is the canonical UTC axis. ``start``/``end`` are
            # Vietnam calendar days, so bound them by the Vietnam day expressed
            # in UTC — same convention ingest uses when deriving ``event_dt``.
            if start is not None:
                sql += " AND event_dt >= ?"
                params.append(
                    to_utc_naive(datetime.datetime.combine(start, datetime.time.min))
                )
            if end is not None:
                sql += " AND event_dt <= ?"
                params.append(
                    to_utc_naive(datetime.datetime.combine(end, datetime.time.max))
                )
            # Newest first so the cap keeps the *recent* window, then re-sorted below.
            sql += f" ORDER BY event_dt DESC LIMIT {capped}"
            return _rows(storage, sql, params)

        rows = await asyncio.to_thread(_read)
        candles = [OHLCVSchema.model_validate(r) for r in rows]
        candles.reverse()
        return candles

    @staticmethod
    async def list_news(
        storage: DuckDBStorage, symbol: str, *, limit: int = 20
    ) -> list[StockNewsSchema]:
        """Recent news for a symbol."""
        capped = _clamp(limit, 20)
        code = symbol.upper()

        def _read() -> list[dict]:
            # Order by the canonical UTC ``event_dt`` (real chronology) rather
            # than the free-form native ``published_at`` string; unparseable
            # rows (event_dt NULL) sort last.
            sql = (
                f"SELECT * FROM {STOCK_NEWS_TABLE} WHERE symbol = ? "  # noqa: S608
                f"ORDER BY event_dt DESC NULLS LAST LIMIT {capped}"
            )
            return _rows(storage, sql, [code])

        rows = await asyncio.to_thread(_read)
        return [StockNewsSchema.model_validate(r) for r in rows]

    # --------------------------------------------------------------- finance
    @staticmethod
    async def list_finance(
        storage: DuckDBStorage,
        symbol: str,
        *,
        report_type: ReportType,
        period: ReportPeriod | None = None,
        limit: int = 20,
    ) -> list[FinanceReportSchema]:
        """Financial reports for a symbol, newest period first."""
        capped = _clamp(limit, 20)
        code = symbol.upper()

        def _read() -> list[dict]:
            sql = f"SELECT * FROM {STOCK_FINANCE_TABLE} WHERE symbol = ? AND report_type = ?"  # noqa: S608
            params: list = [code, str(report_type)]
            if period is not None:
                sql += " AND period = ?"
                params.append(str(period))
            sql += f" ORDER BY year DESC, quarter DESC LIMIT {capped}"
            return _rows(storage, sql, params)

        rows = await asyncio.to_thread(_read)
        return [
            FinanceReportSchema(
                symbol=r["symbol"],
                report_type=r["report_type"],
                period=r["period"],
                year=r.get("year") or 0,
                quarter=r.get("quarter"),
                data=_loads(r.get("data_json")),
                source=r.get("source"),
                synced_at=r.get("synced_at"),
            )
            for r in rows
        ]


def _to_quote(row: dict) -> StockQuoteSchema:
    """Build a quote schema, deriving change vs. the reference price."""
    match_price = row.get("match_price")
    ref_price = row.get("ref_price")
    change = None
    change_pct = None
    if match_price is not None and ref_price:
        # Both come from DECIMAL columns, so these are Decimals. Keep the `100`
        # an int literal — `Decimal * float` raises TypeError.
        change = match_price - ref_price
        change_pct = change / ref_price * 100
    return StockQuoteSchema(
        symbol=row["symbol"],
        match_price=match_price,
        ref_price=ref_price,
        ceiling=row.get("ceiling"),
        floor=row.get("floor"),
        accumulated_volume=row.get("accumulated_volume"),
        change=change,
        change_pct=change_pct,
        source=row.get("source"),
        crawled_at=row.get("crawled_at"),
    )
