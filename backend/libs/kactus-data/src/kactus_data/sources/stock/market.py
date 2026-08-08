"""Batch stock market source for the portfolio crawler.

Wraps vnstock primitives and normalizes their (source-dependent) output into the
stable schemas in :mod:`portfolio_tables`.  ``price_board`` is a true batch call
(many symbols / one request, chunked ~50); news / events / ratios / foreign-trade
are per-symbol and looped resiliently (one failing symbol never aborts the rest).

All vnstock imports are lazy (inside ``_raw_*`` methods) so importing this module
stays cheap and the network calls are isolated behind a single seam that tests
monkeypatch.  Every public method returns a DataFrame whose columns match the
target table exactly (positional INSERT).
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime

import pandas as pd
from kactus_common.database.duckdb.schema import Table
from kactus_common.datetimes import VN_TZ, utcnow_naive
from kactus_data.exceptions import RateLimitedError
from kactus_data.sources.stock.auth import vnstock_min_interval
from kactus_data.util.time import to_event_dt
from loguru import logger

from .portfolio_tables import (
    STOCK_DAILY_SNAPSHOT_TABLE,
    STOCK_EVENTS_TABLE,
    STOCK_FOREIGN_TRADE_TABLE,
    STOCK_NEWS_TABLE,
    STOCK_PRICE_BOARD_TABLE,
    STOCK_RATIOS_TABLE,
)


def _chunks(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten a possibly-MultiIndex column frame to ``a_b`` style names."""
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = ["_".join(str(p) for p in tup if p != "") for tup in df.columns]
    return df


def _pick(row: dict, *names: str, exclude: tuple[str, ...] = ()) -> object | None:
    """First present value among exact keys, then by case-insensitive substring.

    The substring pass is what makes this survive vnstock's column variance
    across sources, but it happily matches a *neighbouring* field when the one
    we asked for is absent. ``exclude`` disqualifies those neighbours by
    substring; callers pass it wherever a near-miss is worse than no value.

    Two live examples, both silent until someone compared against the exchange:
    VCI flattens the matched price to ``match_match_price``, so asking for
    "match_price" fell through to ``match_match_price_ato`` — the opening
    auction price stored as the close (FPT 2026-07-27: 63100 vs the real
    62200). And asking for "url" matched ``news_image_url`` whenever
    ``news_source_link`` was null, pointing every article at its thumbnail.
    """
    for n in names:
        if n in row and pd.notna(row[n]):
            return row[n]
    low = {str(k).lower(): v for k, v in row.items()}
    banned = tuple(e.lower() for e in exclude)
    for n in names:
        for k, v in low.items():
            if any(b in k for b in banned):
                continue
            if n.lower() in k and pd.notna(v):
                return v
    return None


def _to_float(v: object | None) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


# Opening / closing auction fields. They sit right next to the continuous-session
# ones in VCI's flattened board and are a substring match away from being
# mistaken for them.
_AUCTION_FIELDS = ("_ato", "_atc")
# Thumbnail fields on the news feed — never an article link.
_IMAGE_FIELDS = ("image",)


# A column header is a *period* (e.g. "2018", "2018-Q1", "2018Q1") when it
# starts with a 4-digit year.  vnstock 4.x returns the ratio frame transposed —
# financial metrics as rows, periods as columns — so the period labels live in
# the column headers, not in a "period" cell.  Metric-label columns
# (``item`` / ``item_en`` / ``item_id``) never start with a digit.
_PERIOD_RE = re.compile(r"^\d{4}([-_/ ]?Q?[1-4])?$")


def _is_period_col(col: object) -> bool:
    return bool(_PERIOD_RE.match(str(col).strip()))


def _to_table_df(rows: list[dict], table: Table) -> pd.DataFrame:
    """Build a DataFrame with exactly ``table``'s columns, in order.

    Guarantees positional alignment for the register-based INSERT in
    :class:`DatabaseClient`.
    """
    cols = [c.name for c in table.columns]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]


# --------------------------------------------------------------------------- #
# End-of-session snapshot
#
# Units differ *within a single price-board row*, which is the whole reason this
# lives in one function with the constants written down:
#   match_accumulated_value  → MILLIONS of VND (279654.55 == 279.65bn)
#   match_foreign_*_value    → absolute VND    (52667461000 == 52.67bn)
#   prices                   → absolute VND    (62200)
# --------------------------------------------------------------------------- #
ACC_VALUE_UNIT_VND = 1_000_000.0
DEPTH_LEVELS = (1, 2, 3)  # VCI publishes only three levels of the order book


def _depth_sum(raw: dict, side: str) -> float | None:
    """Resting volume on one side of the book, summed over published levels.

    Level-1-only and the 3-level sum differ by an order of magnitude
    (FPT 2026-07-27: 45,000 vs 367,700), so every caller must use this one.
    """
    vols = [_to_float(raw.get(f"bid_ask_{side}_{lvl}_volume")) for lvl in DEPTH_LEVELS]
    present = [v for v in vols if v is not None]
    return sum(present) if present else None


def daily_snapshot(board: pd.DataFrame, *, source: str) -> pd.DataFrame:
    """Price-board rows → one ``stock_daily_snapshot`` row per symbol.

    Pure transform of a frame :meth:`StockMarketSource.price_board` already
    produced — no network call. Reads prices out of ``raw_json`` by exact key
    rather than the normalized columns, so a board stored before the ATO fix
    still yields a correct snapshot.
    """
    cols = [c.name for c in STOCK_DAILY_SNAPSHOT_TABLE.columns]
    if board is None or board.empty:
        return pd.DataFrame(columns=cols)

    now = utcnow_naive()
    fallback_date = datetime.now(VN_TZ).date().isoformat()
    rows: list[dict] = []
    for r in board.to_dict(orient="records"):
        try:
            raw = json.loads(r["raw_json"]) if r.get("raw_json") else {}
        except (TypeError, ValueError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}

        # The board states which session it describes; the wall clock does not.
        session = str(raw.get("listing_trading_date") or "")[:10] or fallback_date
        close = _to_float(raw.get("match_match_price")) or _to_float(
            r.get("match_price")
        )
        ref = (
            _to_float(raw.get("match_reference_price"))
            or _to_float(raw.get("listing_ref_price"))
            or _to_float(r.get("ref_price"))
        )
        volume = _to_float(raw.get("match_accumulated_volume")) or _to_float(
            r.get("accumulated_volume")
        )
        change = close - ref if close is not None and ref else None
        acc_value = _to_float(raw.get("match_accumulated_value"))
        buy_orders = _to_float(raw.get("match_total_buy_orders"))
        sell_orders = _to_float(raw.get("match_total_sell_orders"))
        f_buy = _to_float(raw.get("match_foreign_buy_value"))
        f_sell = _to_float(raw.get("match_foreign_sell_value"))

        rows.append(
            {
                "symbol": r["symbol"],
                "trade_date": session,
                "close_price": close,
                "ref_price": ref,
                "change": change,
                "change_pct": (
                    (change / ref * 100) if change is not None and ref else None
                ),
                "volume": volume,
                "value_vnd": (
                    acc_value * ACC_VALUE_UNIT_VND if acc_value is not None else None
                ),
                "remain_bid": _depth_sum(raw, "bid"),
                "remain_ask": _depth_sum(raw, "ask"),
                # Order counts read 0 during the ATC window — that is "not
                # published", not "zero orders", so leave the average NULL
                # rather than dividing.
                "avg_buy_size": (
                    (volume / buy_orders) if volume and buy_orders else None
                ),
                "avg_sell_size": (
                    (volume / sell_orders) if volume and sell_orders else None
                ),
                "foreign_buy_volume": _to_float(raw.get("match_foreign_buy_volume")),
                "foreign_sell_volume": _to_float(raw.get("match_foreign_sell_volume")),
                "foreign_buy_value": f_buy,
                "foreign_sell_value": f_sell,
                "foreign_net_value": (
                    f_buy - f_sell if f_buy is not None and f_sell is not None else None
                ),
                "current_room": _to_float(raw.get("match_current_room")),
                "total_room": _to_float(raw.get("match_total_room")),
                "source": source,
                "crawled_at": now,
                "raw_json": r.get("raw_json"),
                "event_dt": to_event_dt(session),
            }
        )
    return _to_table_df(rows, STOCK_DAILY_SNAPSHOT_TABLE)


class StockMarketSource:
    """Fetch + normalize stock market data for a list of symbols."""

    def __init__(self, source: str = "VCI", chunk_size: int = 50) -> None:
        self.source = source
        self.chunk_size = chunk_size

    # --------------------------------------------------------------- raw seams
    def _raw_price_board(self, codes: list[str]) -> pd.DataFrame:
        from vnstock import Trading

        return Trading(source=self.source).price_board(symbols_list=codes)

    def _raw_news(self, code: str) -> pd.DataFrame:
        from vnstock import Company

        return Company(symbol=code, source=self.source).news()

    def _raw_events(self, code: str) -> pd.DataFrame:
        from vnstock import Company

        return Company(symbol=code, source=self.source).events()

    def _raw_ratio(self, code: str) -> pd.DataFrame:
        from vnstock import Finance

        return Finance(symbol=code, source=self.source).ratio()

    def _raw_foreign_trade(self, code: str) -> pd.DataFrame:
        from vnstock import Trading

        return Trading(symbol=code, source=self.source).foreign_trade()

    def _raw_all_symbols(self) -> pd.DataFrame:
        from vnstock import Listing

        return Listing(source=self.source).all_symbols()

    def _raw_group(self, group: str) -> pd.Series | pd.DataFrame:
        from vnstock import Listing

        return Listing(source=self.source).symbols_by_group(group)

    # --------------------------------------------------------- normalized API
    def price_board(self, codes: list[str]) -> pd.DataFrame:
        """Latest quote snapshot for ``codes`` (batched, chunked)."""
        now = utcnow_naive()
        rows: list[dict] = []
        interval = vnstock_min_interval()
        done = 0
        for chunk in _chunks(codes, self.chunk_size):
            if done:
                time.sleep(interval)
            try:
                raw = _flatten_columns(self._raw_price_board(chunk))
            except SystemExit as ex:
                logger.warning(
                    f"price_board: vnstock rate limited "
                    f"({done}/{len(codes)} done): {ex}"
                )
                raise RateLimitedError(
                    done=done,
                    total=len(codes),
                    df=_to_table_df(rows, STOCK_PRICE_BOARD_TABLE),
                ) from ex
            except Exception as ex:  # pragma: no cover - network failure path
                logger.warning(f"price_board failed for {chunk}: {ex}")
                continue
            finally:
                done += len(chunk)
            if raw is None or raw.empty:
                continue
            for r in raw.to_dict(orient="records"):
                symbol = _pick(r, "symbol", "ticker", "listing_symbol")
                if not symbol:
                    continue
                rows.append(
                    {
                        "symbol": str(symbol).upper(),
                        # VCI's own flattened names lead, so the exact pass wins
                        # before any substring guessing; ATO/ATC are the auction
                        # prices and must never stand in for the close.
                        "match_price": _to_float(
                            _pick(
                                r,
                                "match_match_price",
                                "match_price",
                                "matchPrice",
                                "close_price",
                                exclude=_AUCTION_FIELDS,
                            )
                        ),
                        "ref_price": _to_float(
                            _pick(
                                r,
                                "match_reference_price",
                                "listing_ref_price",
                                "ref_price",
                                "reference_price",
                                "refPrice",
                            )
                        ),
                        "ceiling": _to_float(
                            _pick(
                                r,
                                "match_ceiling_price",
                                "listing_ceiling",
                                "ceiling",
                                "ceiling_price",
                            )
                        ),
                        "floor": _to_float(
                            _pick(
                                r,
                                "match_floor_price",
                                "listing_floor",
                                "floor",
                                "floor_price",
                            )
                        ),
                        "accumulated_volume": _to_float(
                            _pick(
                                r,
                                "match_accumulated_volume",
                                "accumulated_volume",
                                "total_volume",
                                "volume",
                                exclude=_AUCTION_FIELDS,
                            )
                        ),
                        "source": self.source,
                        "crawled_at": now,
                        "raw_json": json.dumps(r, default=str, ensure_ascii=False),
                    }
                )
        return _to_table_df(rows, STOCK_PRICE_BOARD_TABLE)

    def _per_symbol(
        self, codes: list[str], raw_fn, map_fn, table: Table
    ) -> pd.DataFrame:
        """Loop ``codes`` resiliently; collect normalized rows into ``table``.

        Calls are paced to the active vnstock budget.  A rate-limit hit
        surfaces as :class:`RateLimitedError` carrying the partial frame —
        vnai signals it with ``sys.exit`` (``SystemExit``), which must never
        escape a worker thread (it kills the event loop), and the remaining
        codes would hit the same wall anyway.
        """
        now = utcnow_naive()
        rows: list[dict] = []
        interval = vnstock_min_interval()
        for i, code in enumerate(codes):
            if i:
                time.sleep(interval)
            try:
                raw = raw_fn(code)
            except SystemExit as ex:
                logger.warning(
                    f"{table.name}: vnstock rate limited at {code} "
                    f"({i}/{len(codes)} done): {ex}"
                )
                raise RateLimitedError(
                    done=i, total=len(codes), df=_to_table_df(rows, table)
                ) from ex
            except Exception as ex:  # pragma: no cover - network failure path
                logger.warning(f"{table.name} fetch failed for {code}: {ex}")
                continue
            if raw is None or (hasattr(raw, "empty") and raw.empty):
                continue
            raw = _flatten_columns(raw)
            for r in raw.to_dict(orient="records"):
                mapped = map_fn(code.upper(), r, now)
                if mapped is not None:
                    rows.append(mapped)
        return _to_table_df(rows, table)

    def news(self, codes: list[str]) -> pd.DataFrame:
        def _map(symbol, r, now):
            news_id = _pick(r, "id", "news_id", "rsi") or _pick(
                r, "title", "news_title"
            )
            published_at = _pick(r, "public_date", "published_at", "date")
            return {
                "symbol": symbol,
                "news_id": str(news_id) if news_id is not None else "",
                "title": _pick(r, "title", "news_title", "news_short_content"),
                "published_at": str(published_at or ""),
                # Verified across every stored VCI row: ``news_source_link`` is
                # always null — the feed carries no article URL. Without the
                # exclusion this falls through to ``news_image_url`` and every
                # headline links to its own thumbnail; NULL is the honest answer.
                "url": _pick(
                    r, "news_source_link", "url", "link", exclude=_IMAGE_FIELDS
                ),
                "source": self.source,
                "crawled_at": now,
                # Native ``published_at`` is Vietnam-local; ``event_dt`` is its
                # canonical UTC instant (NULL when unparseable).
                "event_dt": to_event_dt(published_at),
                "raw_json": json.dumps(r, default=str, ensure_ascii=False),
            }

        return self._per_symbol(codes, self._raw_news, _map, STOCK_NEWS_TABLE)

    def events(self, codes: list[str]) -> pd.DataFrame:
        def _map(symbol, r, now):
            event_id = _pick(r, "id", "event_id", "rsi") or _pick(
                r, "event_title", "title"
            )
            event_date = _pick(r, "event_date", "public_date", "date")
            return {
                "symbol": symbol,
                "event_id": str(event_id) if event_id is not None else "",
                "title": _pick(r, "event_title", "title", "event_name"),
                "event_date": str(event_date or ""),
                "source": self.source,
                "crawled_at": now,
                "event_dt": to_event_dt(event_date),
                "raw_json": json.dumps(r, default=str, ensure_ascii=False),
            }

        return self._per_symbol(codes, self._raw_events, _map, STOCK_EVENTS_TABLE)

    def foreign_trade(self, codes: list[str]) -> pd.DataFrame:
        def _map(symbol, r, now):
            trade_date = _pick(r, "trade_date", "date", "time")
            # Fallback label is the Vietnam trading day, not the UTC ``now`` —
            # between 00:00–07:00 VN those disagree by a calendar day.
            native_date = str(trade_date or datetime.now(VN_TZ).date().isoformat())
            return {
                "symbol": symbol,
                "trade_date": native_date,
                "buy_value": _to_float(
                    _pick(r, "buy_value", "foreign_buy_value", "buy")
                ),
                "sell_value": _to_float(
                    _pick(r, "sell_value", "foreign_sell_value", "sell")
                ),
                "net_value": _to_float(_pick(r, "net_value", "net_val", "net")),
                "source": self.source,
                "crawled_at": now,
                "event_dt": to_event_dt(native_date),
                "raw_json": json.dumps(r, default=str, ensure_ascii=False),
            }

        return self._per_symbol(
            codes, self._raw_foreign_trade, _map, STOCK_FOREIGN_TRADE_TABLE
        )

    def ratios(self, codes: list[str], period: str = "quarter") -> pd.DataFrame:
        """Financial ratios → one row per ``(symbol, period)``.

        vnstock 4.x returns the ratio frame **transposed** (metrics as rows,
        periods like ``2025-Q1`` as columns).  We pivot it back: each period
        column becomes one row whose ``raw_json`` is the ``{metric: value}`` map
        for that period.  This keeps the ``(symbol, period)`` primary key unique
        — the pre-pivot shape stamped every row ``period="quarter"`` and blew up
        the UPSERT.  A tidy frame (period already in a cell) falls back to
        one-row-per-record.
        """
        now = utcnow_naive()
        rows: list[dict] = []
        for code in codes:
            try:
                raw = self._raw_ratio(code)
            except Exception as ex:  # pragma: no cover - network failure path
                logger.warning(
                    f"{STOCK_RATIOS_TABLE.name} fetch failed for {code}: {ex}"
                )
                continue
            if raw is None or (hasattr(raw, "empty") and raw.empty):
                continue
            rows.extend(
                self._ratio_rows(code.upper(), _flatten_columns(raw), period, now)
            )
        return _to_table_df(rows, STOCK_RATIOS_TABLE)

    def _ratio_rows(
        self, symbol: str, raw: pd.DataFrame, default_period: str, now: datetime
    ) -> list[dict]:
        cols = list(raw.columns)
        period_cols = [c for c in cols if _is_period_col(c)]
        if period_cols:
            label_col = next(
                (c for c in ("item_id", "item", "item_en") if c in cols), None
            )
            records = raw.to_dict(orient="records")
            out: list[dict] = []
            for p in period_cols:
                metrics = {}
                for r in records:
                    key = r.get(label_col) if label_col else None
                    if key is not None and pd.notna(key):
                        metrics[str(key)] = r.get(p)
                out.append(
                    {
                        "symbol": symbol,
                        "period": str(p).strip(),
                        "source": self.source,
                        "crawled_at": now,
                        "raw_json": json.dumps(
                            metrics, default=str, ensure_ascii=False
                        ),
                    }
                )
            return out
        # Tidy frame: period already in a cell, one row per record.
        out = []
        for r in raw.to_dict(orient="records"):
            label = _pick(r, "period", "yearReport", "year") or default_period
            out.append(
                {
                    "symbol": symbol,
                    "period": str(label),
                    "source": self.source,
                    "crawled_at": now,
                    "raw_json": json.dumps(r, default=str, ensure_ascii=False),
                }
            )
        return out

    # ------------------------------------------------------------- catalog
    def catalog(self) -> list[dict]:
        """All listed symbols, tagged with VN30 / VN100 index membership.

        Returns ``SupportedAssetService.upsert_many`` entries:
        ``{code, name, tags, meta_json}``.
        """
        try:
            raw = _flatten_columns(self._raw_all_symbols())
        except Exception as ex:  # pragma: no cover - network failure path
            logger.warning(f"all_symbols failed: {ex}")
            return []
        if raw is None or raw.empty:
            return []

        tags_by_code: dict[str, list[str]] = {}
        for group in ("VN30", "VN100"):
            for code in self._group_symbols(group):
                tags_by_code.setdefault(code, []).append(group)

        entries: list[dict] = []
        for r in raw.to_dict(orient="records"):
            symbol = _pick(r, "symbol", "ticker")
            if not symbol:
                continue
            code = str(symbol).upper()
            name = _pick(r, "organ_name", "company_name", "organName", "name")
            entries.append(
                {
                    "code": code,
                    "name": name,
                    "tags": tags_by_code.get(code, []),
                    "meta_json": {
                        "exchange": _pick(r, "exchange", "comGroupCode"),
                        "source": self.source,
                    },
                }
            )
        return entries

    def _group_symbols(self, group: str) -> list[str]:
        try:
            res = self._raw_group(group)
        except Exception as ex:  # pragma: no cover - network failure path
            logger.warning(f"symbols_by_group({group}) failed: {ex}")
            return []
        if res is None:
            return []
        if isinstance(res, pd.DataFrame):
            col = "symbol" if "symbol" in res.columns else res.columns[0]
            return [str(s).upper() for s in res[col].tolist()]
        return [str(s).upper() for s in list(res)]
