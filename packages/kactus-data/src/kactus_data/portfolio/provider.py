"""Asset-type strategy: one :class:`AssetProvider` per asset class.

A provider knows how to (a) build the crawlable catalog for its asset type,
(b) crawl a given dataset for a list of codes, and (c) read it back from DuckDB.
The registry maps ``AssetType → provider`` so the scheduler/crawl jobs are
generic: a new asset class is a new provider, not a schema change.

Providers are **synchronous/blocking** (vnstock + DuckDB).  The async crawl
jobs wrap them in ``anyio.to_thread.run_sync`` and gate concurrency.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import date, datetime

from kactus_common.database.duckdb.schema import Table
from kactus_common.portfolio.const import AssetType, CrawlKind
from kactus_data.sources.gold.mihong import MihongGoldSource
from kactus_data.sources.gold.portfolio_tables import GOLD_PRICE_BOARD_TABLE
from kactus_data.sources.stock.market import StockMarketSource, _to_table_df
from kactus_data.sources.stock.portfolio_tables import (
    STOCK_EVENTS_TABLE,
    STOCK_FOREIGN_TRADE_TABLE,
    STOCK_NEWS_TABLE,
    STOCK_PRICE_BOARD_TABLE,
    STOCK_RATIOS_TABLE,
)
from kactus_data.storage.duckdb import DuckDBStorage
from loguru import logger


class AssetProvider(ABC):
    """Per-asset-type ETL strategy."""

    asset_type: AssetType

    @abstractmethod
    def supported_kinds(self) -> set[CrawlKind]:
        """Crawl datasets this provider can produce."""

    @abstractmethod
    def fetch_catalog(self) -> list[dict]:
        """Catalog entries for ``SupportedAssetService.upsert_many`` (blocking)."""

    @abstractmethod
    def crawl(self, kind: CrawlKind, codes: list[str]) -> int:
        """Fetch + store ``kind`` for ``codes``; returns rows written (blocking)."""

    @abstractmethod
    def read(self, kind: CrawlKind, codes: list[str]) -> list[dict]:
        """Read stored ``kind`` rows for ``codes`` from DuckDB (blocking)."""

    # shared DuckDB read helper -------------------------------------------------
    @staticmethod
    def _read_by_column(
        storage: DuckDBStorage, table: Table, column: str, codes: list[str]
    ) -> list[dict]:
        if not codes or not storage.client.table_exists(table.name):
            return []
        safe = ", ".join("'" + str(c).replace("'", "''") + "'" for c in codes)
        df = storage.query(f"SELECT * FROM {table.name} WHERE {column} IN ({safe})")
        return df.to_dict(orient="records") if not df.empty else []


class StockAssetProvider(AssetProvider):
    """STOCK provider — vnstock price board, news, foreign flow, ratios, events."""

    asset_type = AssetType.STOCK

    def __init__(
        self, storage: DuckDBStorage, market: StockMarketSource | None = None
    ) -> None:
        self.storage = storage
        self.market = market or StockMarketSource()
        self._kind_table: dict[CrawlKind, Table] = {
            CrawlKind.QUOTES: STOCK_PRICE_BOARD_TABLE,
            CrawlKind.NEWS: STOCK_NEWS_TABLE,
            CrawlKind.FOREIGN_TRADE: STOCK_FOREIGN_TRADE_TABLE,
            CrawlKind.RATIOS: STOCK_RATIOS_TABLE,
            CrawlKind.EVENTS: STOCK_EVENTS_TABLE,
        }

    def supported_kinds(self) -> set[CrawlKind]:
        return set(self._kind_table)

    def fetch_catalog(self) -> list[dict]:
        return self.market.catalog()

    def crawl(self, kind: CrawlKind, codes: list[str]) -> int:
        if not codes or kind not in self._kind_table:
            return 0
        fetch = {
            CrawlKind.QUOTES: self.market.price_board,
            CrawlKind.NEWS: self.market.news,
            CrawlKind.FOREIGN_TRADE: self.market.foreign_trade,
            CrawlKind.RATIOS: self.market.ratios,
            CrawlKind.EVENTS: self.market.events,
        }[kind]
        df = fetch(codes)
        if df.empty:
            return 0
        return self.storage.store(self._kind_table[kind], df)

    def read(self, kind: CrawlKind, codes: list[str]) -> list[dict]:
        table = self._kind_table.get(kind)
        if table is None:
            return []
        return self._read_by_column(self.storage, table, "symbol", codes)


class GoldAssetProvider(AssetProvider):
    """GOLD provider — mihong.vn quotes. Seeded catalog (SJC, 999, …)."""

    asset_type = AssetType.GOLD
    _SEED = ["SJC", "999", "DOJI", "PNJ"]

    def __init__(self, storage: DuckDBStorage, xsrf_token: str | None = None) -> None:
        self.storage = storage
        self.xsrf_token = xsrf_token or ""

    def supported_kinds(self) -> set[CrawlKind]:
        return {CrawlKind.QUOTES}

    def fetch_catalog(self) -> list[dict]:
        return [{"code": c, "name": c, "tags": [], "meta_json": {}} for c in self._SEED]

    def crawl(self, kind: CrawlKind, codes: list[str]) -> int:
        if kind != CrawlKind.QUOTES or not codes:
            return 0
        if not self.xsrf_token:
            logger.warning("Gold crawl skipped — no mihong XSRF token configured")
            return 0
        source = MihongGoldSource(self.xsrf_token)
        today = date.today()
        now = datetime.now()
        rows: list[dict] = []
        for code in codes:
            resp = source.sync(today, today, code)
            if not resp.success or not resp.data:
                continue
            point = self._latest_point(resp.data)
            rows.append(
                {
                    "code": str(code).upper(),
                    "buy_price": _safe_float(_dig(point, "buyPrice", "buy", "buy_price")),
                    "sell_price": _safe_float(_dig(point, "sellPrice", "sell", "sell_price")),
                    "source": "mihong",
                    "crawled_at": now,
                    "raw_json": json.dumps(point, default=str, ensure_ascii=False),
                }
            )
        df = _to_table_df(rows, GOLD_PRICE_BOARD_TABLE)
        if df.empty:
            return 0
        return self.storage.store(GOLD_PRICE_BOARD_TABLE, df)

    def read(self, kind: CrawlKind, codes: list[str]) -> list[dict]:
        if kind != CrawlKind.QUOTES:
            return []
        return self._read_by_column(self.storage, GOLD_PRICE_BOARD_TABLE, "code", codes)

    @staticmethod
    def _latest_point(data) -> dict:
        """Mihong returns a list/dict of price points; pick the most recent dict."""
        if isinstance(data, dict):
            for key in ("data", "prices", "items", "results"):
                if isinstance(data.get(key), list) and data[key]:
                    return data[key][-1]
            return data
        if isinstance(data, list) and data:
            return data[-1]
        return {}


def _dig(d: dict, *keys: str):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return None


def _safe_float(v) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def build_providers(
    storage: DuckDBStorage,
    *,
    data_source: str = "VCI",
    mihong_token: str | None = None,
) -> dict[AssetType, AssetProvider]:
    """Construct the provider registry (COIN deferred — no provider yet)."""
    return {
        AssetType.STOCK: StockAssetProvider(
            storage, StockMarketSource(source=data_source)
        ),
        AssetType.GOLD: GoldAssetProvider(storage, xsrf_token=mihong_token),
    }
