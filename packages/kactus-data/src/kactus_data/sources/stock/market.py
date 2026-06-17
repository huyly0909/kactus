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
from datetime import datetime

import pandas as pd
from kactus_common.database.duckdb.schema import Table
from loguru import logger

from .portfolio_tables import (
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


def _pick(row: dict, *names: str) -> object | None:
    """First present value among exact keys, then by case-insensitive substring."""
    for n in names:
        if n in row and pd.notna(row[n]):
            return row[n]
    low = {str(k).lower(): v for k, v in row.items()}
    for n in names:
        for k, v in low.items():
            if n.lower() in k and pd.notna(v):
                return v
    return None


def _to_float(v: object | None) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


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
        now = datetime.now()
        rows: list[dict] = []
        for chunk in _chunks(codes, self.chunk_size):
            try:
                raw = _flatten_columns(self._raw_price_board(chunk))
            except Exception as ex:  # pragma: no cover - network failure path
                logger.warning(f"price_board failed for {chunk}: {ex}")
                continue
            if raw is None or raw.empty:
                continue
            for r in raw.to_dict(orient="records"):
                symbol = _pick(r, "symbol", "ticker", "listing_symbol")
                if not symbol:
                    continue
                rows.append(
                    {
                        "symbol": str(symbol).upper(),
                        "match_price": _to_float(_pick(r, "match_price", "matchPrice", "close_price")),
                        "ref_price": _to_float(_pick(r, "ref_price", "reference_price", "refPrice")),
                        "ceiling": _to_float(_pick(r, "ceiling", "ceiling_price")),
                        "floor": _to_float(_pick(r, "floor", "floor_price")),
                        "accumulated_volume": _to_float(
                            _pick(r, "accumulated_volume", "total_volume", "volume")
                        ),
                        "source": self.source,
                        "crawled_at": now,
                        "raw_json": json.dumps(r, default=str, ensure_ascii=False),
                    }
                )
        return _to_table_df(rows, STOCK_PRICE_BOARD_TABLE)

    def _per_symbol(self, codes: list[str], raw_fn, map_fn, table: Table) -> pd.DataFrame:
        """Loop ``codes`` resiliently; collect normalized rows into ``table``."""
        now = datetime.now()
        rows: list[dict] = []
        for code in codes:
            try:
                raw = raw_fn(code)
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
            news_id = _pick(r, "id", "news_id", "rsi") or _pick(r, "title", "news_title")
            return {
                "symbol": symbol,
                "news_id": str(news_id) if news_id is not None else "",
                "title": _pick(r, "title", "news_title", "news_short_content"),
                "published_at": str(_pick(r, "public_date", "published_at", "date") or ""),
                "url": _pick(r, "url", "news_source_link", "link"),
                "source": self.source,
                "crawled_at": now,
                "raw_json": json.dumps(r, default=str, ensure_ascii=False),
            }

        return self._per_symbol(codes, self._raw_news, _map, STOCK_NEWS_TABLE)

    def events(self, codes: list[str]) -> pd.DataFrame:
        def _map(symbol, r, now):
            event_id = _pick(r, "id", "event_id", "rsi") or _pick(r, "event_title", "title")
            return {
                "symbol": symbol,
                "event_id": str(event_id) if event_id is not None else "",
                "title": _pick(r, "event_title", "title", "event_name"),
                "event_date": str(_pick(r, "event_date", "public_date", "date") or ""),
                "source": self.source,
                "crawled_at": now,
                "raw_json": json.dumps(r, default=str, ensure_ascii=False),
            }

        return self._per_symbol(codes, self._raw_events, _map, STOCK_EVENTS_TABLE)

    def foreign_trade(self, codes: list[str]) -> pd.DataFrame:
        def _map(symbol, r, now):
            trade_date = _pick(r, "trade_date", "date", "time")
            return {
                "symbol": symbol,
                "trade_date": str(trade_date or now.date().isoformat()),
                "buy_value": _to_float(_pick(r, "buy_value", "foreign_buy_value", "buy")),
                "sell_value": _to_float(_pick(r, "sell_value", "foreign_sell_value", "sell")),
                "net_value": _to_float(_pick(r, "net_value", "net_val", "net")),
                "source": self.source,
                "crawled_at": now,
                "raw_json": json.dumps(r, default=str, ensure_ascii=False),
            }

        return self._per_symbol(codes, self._raw_foreign_trade, _map, STOCK_FOREIGN_TRADE_TABLE)

    def ratios(self, codes: list[str], period: str = "quarter") -> pd.DataFrame:
        def _map(symbol, r, now):
            label = _pick(r, "period", "yearReport", "year") or period
            return {
                "symbol": symbol,
                "period": str(label),
                "source": self.source,
                "crawled_at": now,
                "raw_json": json.dumps(r, default=str, ensure_ascii=False),
            }

        return self._per_symbol(codes, self._raw_ratio, _map, STOCK_RATIOS_TABLE)

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
