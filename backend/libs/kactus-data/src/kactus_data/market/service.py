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
import math
import re
from decimal import Decimal

import pandas as pd
from kactus_common.database.duckdb.consts import MAX_LIMIT
from kactus_common.datetimes import to_utc_naive
from kactus_data.market import analytics
from kactus_data.market.const import (
    GOLD_BOARD_TABLE,
    GOLD_HISTORY_TABLE,
    STOCK_COMPANY_TABLE,
    STOCK_DAILY_SNAPSHOT_TABLE,
    STOCK_EVENTS_TABLE,
    STOCK_FINANCE_TABLE,
    STOCK_LISTING_TABLE,
    STOCK_NEWS_TABLE,
    STOCK_OHLCV_TABLE,
    STOCK_PRICE_BOARD_TABLE,
    STOCK_RATIOS_TABLE,
)
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_gold.const import DEFAULT_GOLD_HISTORY_LIMIT, GOLD_HISTORY_MAX_LIMIT
from kactus_gold.schema import (
    GoldHistoryCodeSchema,
    GoldHistoryPointSchema,
    GoldPriceSchema,
)
from kactus_stock_vn.const import (
    DEFAULT_DAILY_LIMIT,
    DEFAULT_EVENTS_LIMIT,
    TTM_QUARTERS,
    PeerBasis,
    ReportPeriod,
    ReportType,
    TechnicalInterval,
)
from kactus_stock_vn.schema import (
    AnalystViewSchema,
    CompanySchema,
    FinanceReportSchema,
    FundamentalRadarSchema,
    OHLCVSchema,
    StaleRatiosSchema,
    StockDailyListSchema,
    StockDailySchema,
    StockDetailSchema,
    StockEventSchema,
    StockListingSchema,
    StockNewsSchema,
    StockOverviewSchema,
    StockQuoteSchema,
    StockStatsSchema,
    TechnicalGaugeSchema,
    TTMSchema,
)
from loguru import logger

# Board fields the read models reach into. Kept beside the readers rather than
# imported from the source module: this is the shape of a stored row, and the
# reader must keep working against rows the current crawler no longer writes.
DEPTH_LEVELS = (1, 2, 3)  # VCI publishes three levels of the order book
ACC_VALUE_UNIT_VND = 1_000_000  # board reports accumulated value in millions
_PERIOD_RE = re.compile(r"^(\d{4})(?:[-_/ ]?Q?([1-4]))?$")
# Owners' equity as the balance sheet names it, most specific first.
_EQUITY_KEYS = (
    "owners_equity",
    "owner_s_equity",
    "equity",
    "total_equity",
    "shareholders_equity",
)
_REVENUE_KEYS = ("net_sales", "sales")


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


def _num(v: object | None) -> float | None:
    """Coerce a raw_json value to float, or None if it is not a number."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _dec(v: object) -> Decimal:
    """Money arithmetic stays in Decimal; mixing it with float raises."""
    return v if isinstance(v, Decimal) else Decimal(str(v))


def _depth_sum(raw: dict, side: str) -> float | None:
    """Resting volume on one side of the book, over every published level.

    Level 1 alone and the full sum differ by an order of magnitude, so the
    quote sidebar and the daily table must not each pick their own.
    """
    vols = [_num(raw.get(f"bid_ask_{side}_{lvl}_volume")) for lvl in DEPTH_LEVELS]
    present = [v for v in vols if v is not None]
    return sum(present) if present else None


def _period_key(label: str) -> tuple[int, int]:
    """Sortable ``(year, quarter)`` from "2025" / "2025-Q3".

    A full-year row sorts *after* Q4 of the same year so it wins as "latest"
    over the quarters it already contains.
    """
    m = _PERIOD_RE.match(str(label).strip())
    if not m:
        return (0, 0)
    return (int(m.group(1)), int(m.group(2)) if m.group(2) else 5)


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
        """Latest quote per ``(code, source)`` (optionally filtered by code).

        The board is keyed ``(code, source)``, so **one code can return several
        rows** — SJC and mihong both quote 999, as different products. Ordering
        by both keys keeps a code's sources adjacent and the result stable.
        """

        def _read() -> list[dict]:
            sql = f"SELECT * FROM {GOLD_BOARD_TABLE}"  # noqa: S608 - fixed table name
            params: list = []
            if codes:
                placeholders = ", ".join("?" for _ in codes)
                sql += f" WHERE code IN ({placeholders})"
                params = list(codes)
            sql += " ORDER BY code, source"
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
        source: str | None = None,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
        limit: int = DEFAULT_GOLD_HISTORY_LIMIT,
    ) -> list[GoldHistoryPointSchema]:
        """Daily points for one gold series, oldest → newest (newest *limit*).

        Series identity is ``(source, code)``. Without ``source`` a code served
        by several feeds (SJC-999 vs Mihong-999) returns **both** interleaved —
        two points per date — and ``limit`` is then spent across all of them, so
        a caller charting one series must pass ``source``.

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
            if source is not None:
                sql += " AND source = ?"
                params.append(source)
            if start is not None:
                sql += " AND date >= ?"
                params.append(start)
            if end is not None:
                sql += " AND date <= ?"
                params.append(end)
            # Newest first so the cap keeps the *recent* window, then re-sorted
            # below. ``source`` breaks the tie so an unfiltered multi-source
            # read is at least deterministic rather than arbitrary.
            sql += f" ORDER BY date DESC, source LIMIT {capped}"
            return _rows(storage, sql, params)

        rows = await asyncio.to_thread(_read)
        points = [GoldHistoryPointSchema.model_validate(r) for r in rows]
        points.reverse()
        return points

    @staticmethod
    async def list_gold_history_codes(
        storage: DuckDBStorage,
    ) -> list[GoldHistoryCodeSchema]:
        """Catalogue of stored gold series (source, code, unit, span, points).

        One entry per ``(source, code, unit)`` — grouping on ``code`` alone
        merged SJC-999 into Mihong-999, summing their point counts and spanning
        the union of their dates, which left the UI's picker unable to tell the
        two series apart.
        """

        def _read() -> list[dict]:
            sql = (
                "SELECT source, code, unit, count(*) AS points, "
                "min(date) AS first_date, max(date) AS last_date, "
                "any_value(location) AS location, any_value(gold_type) AS gold_type "
                f"FROM {GOLD_HISTORY_TABLE} "  # noqa: S608
                "GROUP BY source, code, unit ORDER BY source, code"
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

    # ------------------------------------------------------- stock detail
    @staticmethod
    async def list_events(
        storage: DuckDBStorage, symbol: str, *, limit: int = DEFAULT_EVENTS_LIMIT
    ) -> list[StockEventSchema]:
        """Corporate events for a symbol, newest first."""
        capped = _clamp(limit, DEFAULT_EVENTS_LIMIT)
        code = symbol.upper()

        def _read() -> list[dict]:
            # Order by the canonical UTC ``event_dt`` rather than the free-form
            # native ``event_date`` string; unparseable rows sort last.
            sql = (
                f"SELECT * FROM {STOCK_EVENTS_TABLE} WHERE symbol = ? "  # noqa: S608
                f"ORDER BY event_dt DESC NULLS LAST LIMIT {capped}"
            )
            return _rows(storage, sql, [code])

        rows = await asyncio.to_thread(_read)
        out: list[StockEventSchema] = []
        for r in rows:
            raw = _loads(r.get("raw_json"))
            out.append(
                StockEventSchema(
                    symbol=r["symbol"],
                    event_id=r.get("event_id"),
                    title=r.get("title"),
                    event_date=r.get("event_date"),
                    category=raw.get("category"),
                    event_name=raw.get("event_name_vi") or raw.get("event_name_en"),
                    exright_date=_opt_str(raw.get("exright_date")),
                    record_date=_opt_str(raw.get("record_date")),
                    value_per_share=_num(raw.get("value_per_share")),
                    source=r.get("source"),
                )
            )
        return out

    @staticmethod
    async def list_daily(
        storage: DuckDBStorage, symbol: str, *, limit: int = DEFAULT_DAILY_LIMIT
    ) -> StockDailyListSchema:
        """Per-session trading table: candles left-joined onto EOD snapshots.

        Candles carry price/volume for the whole stored history; the snapshot
        supplies traded value, book depth and foreign flow, and only for
        sessions actually captured — so those columns are NULL further back and
        ``snapshot_from`` tells the client where the series really starts.
        """
        capped = _clamp(limit, DEFAULT_DAILY_LIMIT)
        code = symbol.upper()

        def _read() -> tuple[list[dict], str | None]:
            rows = _rows(
                storage,
                # One extra row so the oldest row shown still has a previous
                # close to compute its change against.
                f"""
                SELECT CAST(o.event_dt AS DATE) AS trade_date,
                       o.open, o.high, o.low, o.close, o.volume,
                       s.value_vnd, s.remain_bid, s.remain_ask,
                       s.avg_buy_size, s.avg_sell_size,
                       s.foreign_buy_volume, s.foreign_sell_volume,
                       s.foreign_buy_value, s.foreign_sell_value,
                       s.foreign_net_value
                FROM {STOCK_OHLCV_TABLE} o
                LEFT JOIN {STOCK_DAILY_SNAPSHOT_TABLE} s
                       ON s.symbol = o.symbol
                      AND s.trade_date = CAST(o.event_dt AS DATE)::VARCHAR
                WHERE o.symbol = ? AND o.interval = ?
                ORDER BY o.event_dt DESC
                LIMIT {capped + 1}
                """,  # noqa: S608 - table names are module constants
                [code, str(TechnicalInterval.D1)],
            )
            first = _rows(
                storage,
                "SELECT min(trade_date) AS d FROM "  # noqa: S608
                f"{STOCK_DAILY_SNAPSHOT_TABLE} WHERE symbol = ?",
                [code],
            )
            return rows, (first[0].get("d") if first else None)

        rows, snapshot_from = await asyncio.to_thread(_read)
        out: list[StockDailySchema] = []
        for i, r in enumerate(rows[:capped]):
            close = r.get("close")
            prev = rows[i + 1].get("close") if i + 1 < len(rows) else None
            change = (
                _dec(close) - _dec(prev)
                if close is not None and prev is not None
                else None
            )
            out.append(
                StockDailySchema(
                    symbol=code,
                    trade_date=str(r["trade_date"]),
                    open=r.get("open"),
                    high=r.get("high"),
                    low=r.get("low"),
                    close=close,
                    change=change,
                    change_pct=(
                        float(change) / float(prev) * 100
                        if change is not None and prev
                        else None
                    ),
                    volume=r.get("volume"),
                    value_vnd=r.get("value_vnd"),
                    remain_bid=r.get("remain_bid"),
                    remain_ask=r.get("remain_ask"),
                    avg_buy_size=r.get("avg_buy_size"),
                    avg_sell_size=r.get("avg_sell_size"),
                    foreign_buy_volume=r.get("foreign_buy_volume"),
                    foreign_sell_volume=r.get("foreign_sell_volume"),
                    foreign_buy_value=r.get("foreign_buy_value"),
                    foreign_sell_value=r.get("foreign_sell_value"),
                    foreign_net_value=r.get("foreign_net_value"),
                )
            )
        return StockDailyListSchema(
            symbol=code,
            rows=out,
            snapshot_from=_opt_str(snapshot_from),
            proprietary_supported=False,
        )

    @staticmethod
    async def get_technical(
        storage: DuckDBStorage,
        symbol: str,
        *,
        interval: TechnicalInterval = TechnicalInterval.D1,
    ) -> TechnicalGaugeSchema:
        """Indicator consensus for a symbol, derived from stored candles.

        Weekly and monthly readings are rolled up from dailies, so all three
        intervals read the same rows — the full stored history, because a
        200-period average needs it.
        """
        code = symbol.upper()

        def _read() -> pd.DataFrame:
            return _ohlcv_frame(storage, code)

        df = await asyncio.to_thread(_read)
        result = await asyncio.to_thread(analytics.technical_gauge, df, str(interval))
        return TechnicalGaugeSchema(symbol=code, **result)

    @staticmethod
    async def get_fundamental(
        storage: DuckDBStorage, symbol: str
    ) -> FundamentalRadarSchema:
        """Five-axis fundamental score for a symbol vs. comparable peers."""
        code = symbol.upper()

        def _read() -> tuple[pd.DataFrame, str | None, bool, PeerBasis, str | None]:
            peers, sector, is_bank, basis = _peer_group(storage, code)
            if code not in peers:
                peers = [*peers, code]
            frame = _peer_ratio_frame(storage, peers)
            as_of, _ = _latest_ratios(storage, code)
            return frame, sector, is_bank, basis, as_of

        frame, sector, is_bank, basis, as_of = await asyncio.to_thread(_read)
        result = analytics.fundamental_radar(frame, code, is_bank=is_bank)
        return FundamentalRadarSchema(
            **result,
            sector=sector,
            basis=basis,
            as_of=as_of,
            peer_symbols=sorted(frame.index.tolist()) if not frame.empty else [],
        )

    @staticmethod
    async def get_overview(
        storage: DuckDBStorage, symbol: str, *, benchmark: str = "VNINDEX"
    ) -> StockOverviewSchema | None:
        """Header + sidebar for the detail page, in one read.

        Returns ``None`` only when the symbol is absent from every source
        table, matching :meth:`get_stock`.
        """
        code = symbol.upper()

        def _read() -> dict:
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
            board = _rows(
                storage,
                f"SELECT * FROM {STOCK_PRICE_BOARD_TABLE} WHERE symbol = ?",  # noqa: S608
                [code],
            )
            ratio_period, ratios = _latest_ratios(storage, code)
            year_ago = datetime.date.today() - datetime.timedelta(days=365)
            return {
                "listing": listing,
                "company": company,
                "board": board,
                "ratio_period": ratio_period,
                "ratios": ratios,
                "income": _income_quarters(storage, code),
                "equity": _latest_equity(storage, code),
                "hist": _ohlcv_frame(storage, code, start=year_ago),
                "bench": _ohlcv_frame(
                    storage,
                    benchmark,
                    start=datetime.date.today() - datetime.timedelta(days=730),
                ),
                "long_hist": _ohlcv_frame(
                    storage,
                    code,
                    start=datetime.date.today() - datetime.timedelta(days=730),
                ),
            }

        d = await asyncio.to_thread(_read)
        if not d["listing"] and not d["company"] and not d["board"]:
            return None

        profile = _loads(d["company"][0].get("raw_json")) if d["company"] else {}
        quote = _to_quote(d["board"][0]) if d["board"] else None
        ratios = d["ratios"]
        ttm, fy = _roll_up(d["income"])
        equity, equity_period = d["equity"]

        price = _num(quote.match_price) if quote else _num(profile.get("current_price"))
        shares = _num(profile.get("issue_share")) or _num(
            ratios.get("outstanding_shares")
        )

        # Multiples come from price × trailing statements, never from the ratio
        # feed: on a restricted tier that feed can be frozen years back, and a
        # P/E from then is not stale, it is wrong. The feed values still travel,
        # in ``stale_ratios``, always with their period attached.
        eps = bvps = pe = pb = ps = roe = None
        if ttm is not None and shares:
            earnings = _num(ttm.profit_attributable) or _num(ttm.profit)
            if earnings:
                eps = earnings / shares
                pe = price / eps if price and eps else None
                roe = earnings / float(equity) if equity else None
            revenue = _num(ttm.revenue)
            if revenue and price:
                ps = (price * shares) / revenue
        if equity and shares:
            bvps = float(equity) / shares
            pb = price / bvps if price and bvps else None

        hist, bench, long_hist = d["hist"], d["bench"], d["long_hist"]
        beta = (
            analytics.beta(long_hist["close"], bench["close"])
            if not bench.empty and not long_hist.empty
            else None
        )
        # 52-week band recomputed from candles; the company profile publishes it
        # too but goes stale between crawls.
        high_52w = float(hist["high"].max()) if not hist.empty else None
        low_52w = float(hist["low"].min()) if not hist.empty else None
        avg_vol = float(hist["volume"].mean()) if not hist.empty else None

        return StockOverviewSchema(
            symbol=code,
            organ_name=(d["listing"][0].get("organ_name") if d["listing"] else None)
            or profile.get("organ_name"),
            short_name=profile.get("organ_short_name"),
            sector=profile.get("sector"),
            exchange=profile.get("com_group_code"),
            profile=profile.get("company_profile"),
            listing_date=_opt_str(profile.get("listing_date")),
            quote=quote,
            stats=StockStatsSchema(
                pe=pe,
                pb=pb,
                ps=ps,
                eps=eps,
                bvps=bvps,
                roe=roe,
                equity=equity,
                equity_period=equity_period,
                market_cap=(
                    _dec(price) * _dec(shares)
                    if price and shares
                    else _num(profile.get("market_cap"))
                ),
                outstanding_shares=shares,
                free_float_pct=_num(profile.get("free_float_percentage")),
                dividend_per_share=_num(profile.get("dividend_per_share_tsr")),
                dividend_yield=_num(ratios.get("dividend_yield")),
                foreign_owned_pct=_num(profile.get("foreigner_percentage")),
                foreign_room_pct=_num(profile.get("maximum_foreign_percentage")),
                state_pct=_num(profile.get("state_percentage")),
                high_52w=high_52w or _num(profile.get("highest_price1_year")),
                low_52w=low_52w or _num(profile.get("lowest_price1_year")),
                avg_volume_52w=avg_vol,
                beta=beta,
            ),
            stale_ratios=(
                StaleRatiosSchema(
                    period=d["ratio_period"],
                    pe=_num(ratios.get("pe_ratio")),
                    pb=_num(ratios.get("pb_ratio")),
                    ps=_num(ratios.get("ps_ratio")),
                    roe=_num(ratios.get("roe")),
                    roa=_num(ratios.get("roa")),
                )
                if ratios
                else None
            ),
            analyst=(
                AnalystViewSchema(
                    rating=profile.get("rating"),
                    target_price=_num(profile.get("target_price")),
                    upside_pct=_num(profile.get("upside_to_target_percent")),
                    analyst=profile.get("analyst"),
                    rating_as_of=_opt_str(profile.get("rating_as_of")),
                )
                if profile.get("rating") or profile.get("target_price")
                else None
            ),
            ttm=ttm,
            fy=fy,
        )


# --------------------------------------------------------------------------- #
# Stock-detail read helpers — blocking; callers hop to a thread.
# --------------------------------------------------------------------------- #
def _opt_str(v: object | None) -> str | None:
    """Stringify, mapping NULL/NaN placeholders to None.

    vnstock leaves absent dates as the float NaN inside ``raw_json``, which
    would otherwise reach the client as the literal string "nan".
    """
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    s = str(v)
    return None if s.strip().lower() in {"", "nan", "nat", "none"} else s


def _ohlcv_frame(
    storage: DuckDBStorage, symbol: str, *, start: datetime.date | None = None
) -> pd.DataFrame:
    """Stored daily candles → a time-indexed frame for the analytics module."""
    sql = (
        "SELECT event_dt, open, high, low, close, volume "
        f"FROM {STOCK_OHLCV_TABLE} WHERE symbol = ? AND interval = ?"  # noqa: S608
    )
    params: list = [symbol.upper(), str(TechnicalInterval.D1)]
    if start is not None:
        sql += " AND event_dt >= ?"
        params.append(to_utc_naive(datetime.datetime.combine(start, datetime.time.min)))
    rows = _rows(storage, sql + " ORDER BY event_dt", params)
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows).set_index("event_dt")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _latest_ratios(storage: DuckDBStorage, symbol: str) -> tuple[str | None, dict]:
    """Most recent ratio period for a symbol → ``(period label, metrics)``."""
    rows = _rows(
        storage,
        f"SELECT period, raw_json FROM {STOCK_RATIOS_TABLE} WHERE symbol = ?",  # noqa: S608
        [symbol.upper()],
    )
    if not rows:
        return None, {}
    best = max(rows, key=lambda r: _period_key(r.get("period") or ""))
    return best.get("period"), _loads(best.get("raw_json"))


def _peer_ratio_frame(storage: DuckDBStorage, symbols: list[str]) -> pd.DataFrame:
    """Latest ratio metrics for many symbols → one row each, indexed by symbol."""
    records = {}
    for sym in symbols:
        _period, metrics = _latest_ratios(storage, sym)
        if metrics:
            records[sym.upper()] = metrics
    if not records:
        return pd.DataFrame()
    return pd.DataFrame.from_dict(records, orient="index")


def _is_bank(storage: DuckDBStorage, symbol: str) -> bool:
    rows = _rows(
        storage,
        f"SELECT raw_json FROM {STOCK_COMPANY_TABLE} WHERE symbol = ?",  # noqa: S608
        [symbol.upper()],
    )
    return bool(_loads(rows[0].get("raw_json")).get("is_bank")) if rows else False


def _peer_group(
    storage: DuckDBStorage, symbol: str
) -> tuple[list[str], str | None, bool, PeerBasis]:
    """Comparable symbols for a fundamental ranking.

    Prefers the symbol's own sector and widens to the rest of the board when
    that sector is too thin to rank against. The bank / non-bank split is not
    part of that fallback — it holds either way. Ranking a tech company's
    ``current_ratio`` against a bank's is meaningless in both directions, and
    banks are a large minority of the large-cap board, so an unfiltered
    fallback would quietly score every industrial name against a banking cohort.
    """
    rows = _rows(
        storage,
        f"SELECT symbol, raw_json FROM {STOCK_COMPANY_TABLE}",  # noqa: S608
    )
    profiles = {r["symbol"]: _loads(r.get("raw_json")) for r in rows}
    me = profiles.get(symbol.upper(), {})
    sector = me.get("sector") or me.get("icb_code_lv2")
    is_bank = bool(me.get("is_bank"))

    comparable = [s for s, p in profiles.items() if bool(p.get("is_bank")) == is_bank]
    if sector:
        same = [
            s
            for s in comparable
            if (profiles[s].get("sector") or profiles[s].get("icb_code_lv2")) == sector
        ]
        if len(same) >= analytics.MIN_PEERS:
            return same, sector, is_bank, PeerBasis.SECTOR
    basis = PeerBasis.VN30_BANKS if is_bank else PeerBasis.VN30_NONBANK
    return comparable, sector, is_bank, basis


def _income_quarters(storage: DuckDBStorage, symbol: str) -> list[dict]:
    """Quarterly income statements for a symbol, newest first."""
    return _rows(
        storage,
        f"SELECT period, year, quarter, data_json FROM {STOCK_FINANCE_TABLE} "  # noqa: S608
        "WHERE symbol = ? AND report_type = ? AND quarter BETWEEN 1 AND 4 "
        "ORDER BY year DESC, quarter DESC",
        [symbol.upper(), str(ReportType.INCOME_STATEMENT)],
    )


def _sum_quarters(quarters: list[dict], *, year: int | None = None) -> TTMSchema:
    revenue = attributable = after_tax = 0.0
    for q in quarters:
        m = _loads(q.get("data_json"))
        for key in _REVENUE_KEYS:
            v = _num(m.get(key))
            if v is not None:
                revenue += v
                break
        attributable += _num(m.get("attributable_to_parent_company")) or 0.0
        after_tax += _num(m.get("net_profit_loss_after_tax")) or 0.0
    return TTMSchema(
        quarters=len(quarters),
        partial=len(quarters) < TTM_QUARTERS,
        period_from=quarters[-1].get("period") if quarters else None,
        period_to=quarters[0].get("period") if quarters else None,
        year=year,
        revenue=revenue,
        profit=after_tax,
        profit_attributable=attributable,
    )


def _roll_up(quarters: list[dict]) -> tuple[TTMSchema | None, TTMSchema | None]:
    """``(trailing twelve months, last complete fiscal year)``.

    TTM is the four most recent quarters — the most current view. ``fy`` is the
    newest year with all four quarters stored, which is what published
    "full-year" figures refer to; the two differ whenever the year is part-way
    through, so both travel rather than the caller guessing which it has.
    """
    if not quarters:
        return None, None
    ttm = _sum_quarters(quarters[:TTM_QUARTERS])

    by_year: dict[int, list[dict]] = {}
    for q in quarters:
        by_year.setdefault(int(q.get("year") or 0), []).append(q)
    complete = sorted(
        (y for y, qs in by_year.items() if y and len(qs) == TTM_QUARTERS), reverse=True
    )
    fy = (
        _sum_quarters(
            sorted(by_year[complete[0]], key=lambda q: -int(q.get("quarter") or 0)),
            year=complete[0],
        )
        if complete
        else None
    )
    return ttm, fy


def _latest_equity(
    storage: DuckDBStorage, symbol: str
) -> tuple[Decimal | None, str | None]:
    """Owners' equity from the newest balance sheet → ``(value, period)``."""
    rows = _rows(
        storage,
        f"SELECT period, data_json FROM {STOCK_FINANCE_TABLE} "  # noqa: S608
        "WHERE symbol = ? AND report_type = ? ORDER BY year DESC, quarter DESC LIMIT 1",
        [symbol.upper(), str(ReportType.BALANCE_SHEET)],
    )
    if not rows:
        return None, None
    period = rows[0].get("period")
    metrics = _loads(rows[0].get("data_json"))
    for key in _EQUITY_KEYS:
        v = _num(metrics.get(key))
        if v:
            return _dec(v), period
    return None, period


def _to_quote(row: dict) -> StockQuoteSchema:
    """Build a quote schema, deriving change vs. the reference price."""
    raw = _loads(row.get("raw_json"))
    # The board's own flattened close beats the normalized column: rows written
    # before the ATO fix hold the opening-auction price there.
    match_price = _num(raw.get("match_match_price"))
    if match_price is None:
        match_price = row.get("match_price")
    ref_price = row.get("ref_price")
    change = None
    change_pct = None
    if match_price is not None and ref_price:
        # Both come from DECIMAL columns, so these are Decimals. Keep the `100`
        # an int literal — `Decimal * float` raises TypeError.
        change = _dec(match_price) - _dec(ref_price)
        change_pct = float(change) / float(ref_price) * 100
    acc_value = _num(raw.get("match_accumulated_value"))
    return StockQuoteSchema(
        symbol=row["symbol"],
        match_price=match_price,
        ref_price=ref_price,
        ceiling=row.get("ceiling"),
        floor=row.get("floor"),
        accumulated_volume=row.get("accumulated_volume"),
        change=change,
        change_pct=change_pct,
        open=_num(raw.get("match_open_price")),
        high=_num(raw.get("match_highest")),
        low=_num(raw.get("match_lowest")),
        # Board publishes accumulated value in millions of VND.
        value_vnd=(acc_value * ACC_VALUE_UNIT_VND if acc_value is not None else None),
        remain_bid=_depth_sum(raw, "bid"),
        remain_ask=_depth_sum(raw, "ask"),
        foreign_buy_volume=_num(raw.get("match_foreign_buy_volume")),
        foreign_sell_volume=_num(raw.get("match_foreign_sell_volume")),
        source=row.get("source"),
        crawled_at=row.get("crawled_at"),
    )
