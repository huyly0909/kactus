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
from kactus_common.datetimes import utcnow_naive
from kactus_common.portfolio.const import AssetType, CrawlKind
from kactus_data.sources.gold.mihong import CHI_TO_LUONG as MIHONG_CHI_TO_LUONG
from kactus_data.sources.gold.mihong import SUPPORTED_CODES as MIHONG_CODES
from kactus_data.sources.gold.mihong import MihongGoldSource
from kactus_data.sources.gold.portfolio_tables import (
    BOARD_SOURCE_PRIORITY,
    GOLD_PRICE_BOARD_TABLE,
    GOLD_PRICE_TICK_TABLE,
    MIHONG_BOARD_CODES,
    UNIT_USD_PER_OZ,
    UNIT_VND_PER_LUONG,
)
from kactus_data.sources.gold.sjc import SjcGoldSource
from kactus_data.sources.gold.yahoo import CODE as XAU_CODE
from kactus_data.sources.gold.yahoo import YahooGoldSource
from kactus_data.sources.stock.market import StockMarketSource, _to_table_df
from kactus_data.sources.stock.portfolio_tables import (
    STOCK_EVENTS_TABLE,
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
    """STOCK provider — vnstock price board, news, ratios, events.

    ``foreign_trade`` is intentionally NOT wired: vnstock 4.x serves stock data via
    VCI, which does not implement foreign-flow (raises ``NotImplementedError``) — it
    was only available from the now-dead TCBS provider. The enum/table/market method
    are kept dormant so it can be re-enabled if a source ever provides it.
    """

    asset_type = AssetType.STOCK

    def __init__(
        self,
        storage: DuckDBStorage,
        market: StockMarketSource | None = None,
        decision_market: StockMarketSource | None = None,
    ) -> None:
        self.storage = storage
        # ``market`` serves quotes + catalog (settings source, e.g. KBS).
        # ``decision_market`` serves news/events/ratios — these are near-empty on
        # KBS (news≈1, events=0 live) but rich on VCI, so they are routed to a
        # dedicated VCI-backed source regardless of the quotes source.
        self.market = market or StockMarketSource()
        self.decision_market = decision_market or StockMarketSource(source="VCI")
        self._kind_table: dict[CrawlKind, Table] = {
            CrawlKind.QUOTES: STOCK_PRICE_BOARD_TABLE,
            CrawlKind.NEWS: STOCK_NEWS_TABLE,
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
            CrawlKind.NEWS: self.decision_market.news,
            CrawlKind.RATIOS: self.decision_market.ratios,
            CrawlKind.EVENTS: self.decision_market.events,
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
    """GOLD provider — SJC-official quotes plus mihong.vn.

    sjc.com.vn is the issuer of the domestic reference price, so it leads.
    mihong plays **two** roles: an independent series for
    ``MIHONG_BOARD_CODES`` (SJC and mihong both quote 999, as different
    products), and the fallback for any domestic code whenever the SJC board
    is unreachable (it sits behind Cloudflare).  ``gold_price_board`` is keyed
    ``(code, source)`` and keeps every series side by side; choosing one quote
    per code happens at read time, in :func:`_preferred_gold_rows`.

    Every price stored in ``gold_price_board`` is **VND per lượng** — mihong
    quotes per chỉ and is scaled on the way in, so rows stay comparable
    across sources.

    The catalog is the three codes with a wired feed — SJC bar, 999 ring, and
    world gold (XAU). DOJI/PNJ were dropped: no free daily feed, and the SJC
    board already publishes the authoritative domestic reference.
    """

    asset_type = AssetType.GOLD

    _NAMES = {
        "SJC": "Vàng miếng SJC",
        "999": "Vàng nhẫn 99,99%",
        XAU_CODE: "Vàng thế giới (XAU/USD)",
    }
    #: Codes with a working daily feed — every seeded code is crawlable now that
    #: DOJI/PNJ are gone; ``_ENABLED`` still gates ``fetch_catalog`` for clarity.
    _ENABLED = frozenset({"SJC", "999", XAU_CODE})
    _SEED = ["SJC", "999", XAU_CODE]

    def __init__(self, storage: DuckDBStorage, xsrf_token: str | None = None) -> None:
        self.storage = storage
        # Retained for backwards compatibility: the current mihong endpoint is
        # unauthenticated, so gold no longer needs a token to crawl.
        self.xsrf_token = xsrf_token or ""

    def supported_kinds(self) -> set[CrawlKind]:
        return {CrawlKind.QUOTES}

    def fetch_catalog(self) -> list[dict]:
        entries = []
        for code in self._SEED:
            enabled = code in self._ENABLED
            meta = {
                "enabled": enabled,
                "unit": UNIT_USD_PER_OZ if code == XAU_CODE else UNIT_VND_PER_LUONG,
            }
            if not enabled:
                meta["disabled_reason"] = "No free daily price feed wired yet"
            entries.append(
                {
                    "code": code,
                    "name": self._NAMES.get(code, code),
                    # Listed either way so the UI can show it greyed out rather
                    # than silently hiding a gold type users expect to see.
                    "is_crawlable": enabled,
                    "tags": [] if enabled else ["disabled"],
                    "meta_json": meta,
                }
            )
        return entries

    def crawl(self, kind: CrawlKind, codes: list[str]) -> int:
        if kind != CrawlKind.QUOTES or not codes:
            return 0

        wanted = [str(c).upper() for c in codes]
        today = date.today()
        now = utcnow_naive()

        # Only reach for the domestic sources if a domestic code was asked for;
        # one SJC request prices every code SJC publishes.
        domestic = [c for c in wanted if c != XAU_CODE]
        sjc = SjcGoldSource()
        sjc_board = sjc.fetch_board() if domestic else []
        mihong = MihongGoldSource()

        rows: list[dict] = []
        for code in wanted:
            if code == XAU_CODE:
                got = [self._yahoo_row(YahooGoldSource(), now)]
            else:
                sjc_row = self._sjc_row(sjc, code, sjc_board, now)
                # Not a short-circuit any more: with the board keyed
                # (code, source), mihong's 999 is its own series and must be
                # refreshed by every crawl or it goes permanently stale. It is
                # still *also* the fallback when SJC yields nothing.
                mihong_row = (
                    self._mihong_row(mihong, code, today, now)
                    if code in MIHONG_BOARD_CODES or sjc_row is None
                    else None
                )
                got = [sjc_row, mihong_row]
            fetched = [r for r in got if r is not None]
            if not fetched:
                logger.debug("No gold quote available for {code}", code=code)
                continue
            rows.extend(fetched)

        df = _to_table_df(rows, GOLD_PRICE_BOARD_TABLE)
        if df.empty:
            return 0
        stored = self.storage.store(GOLD_PRICE_BOARD_TABLE, df)
        # Every crawl also logs a tick (decision #6): the board rows already
        # carry every tick column, so the hourly scheduler accumulates an
        # intraday trail with no extra fetch. PK (code, source, crawled_at)
        # keeps each crawl distinct; the board keeps only the latest per
        # (code, source). ``stored`` can exceed ``len(codes)`` — a dual-sourced
        # code writes one row per source.
        self.storage.store(
            GOLD_PRICE_TICK_TABLE, _to_table_df(rows, GOLD_PRICE_TICK_TABLE)
        )
        return stored

    @staticmethod
    def _sjc_row(
        sjc: SjcGoldSource, code: str, board: list[dict], now: datetime
    ) -> dict | None:
        """Board row from sjc.com.vn (already VND/lượng), or ``None``."""
        if not board:
            return None
        quote = sjc.quote(code, board=board)
        if quote is None:
            return None
        if quote["buy_price"] is None and quote["sell_price"] is None:
            return None
        return {
            "code": str(code).upper(),
            "buy_price": quote["buy_price"],
            "sell_price": quote["sell_price"],
            "unit": UNIT_VND_PER_LUONG,
            "source": SjcGoldSource.name,
            "crawled_at": now,
            "raw_json": json.dumps(quote["raw"], default=str, ensure_ascii=False),
        }

    @classmethod
    def _mihong_row(
        cls, mihong: MihongGoldSource, code: str, today: date, now: datetime
    ) -> dict | None:
        """Board row from mihong, scaled VND/chỉ → VND/lượng, or ``None``."""
        if str(code).upper() not in MIHONG_CODES:
            return None
        resp = mihong.sync(today, today, code)
        if not resp.success or not resp.data:
            return None
        point = cls._latest_point(resp.data)
        buy = _safe_float(_dig(point, "buyingPrice", "buyPrice", "buy", "buy_price"))
        sell = _safe_float(
            _dig(point, "sellingPrice", "sellPrice", "sell", "sell_price")
        )
        if buy is None and sell is None:
            return None
        return {
            "code": str(code).upper(),
            "buy_price": None if buy is None else buy * MIHONG_CHI_TO_LUONG,
            "sell_price": None if sell is None else sell * MIHONG_CHI_TO_LUONG,
            "unit": UNIT_VND_PER_LUONG,
            "source": mihong.name,
            "crawled_at": now,
            "raw_json": json.dumps(point, default=str, ensure_ascii=False),
        }

    @staticmethod
    def _yahoo_row(yahoo: YahooGoldSource, now: datetime) -> dict | None:
        """World gold row (USD/oz).  Spot has no dealer spread → buy == sell."""
        bar = yahoo.latest()
        if bar is None or bar.get("close") is None:
            return None
        close = _safe_float(bar["close"])
        return {
            "code": XAU_CODE,
            "buy_price": close,
            "sell_price": close,
            "unit": UNIT_USD_PER_OZ,
            "source": yahoo.name,
            "crawled_at": now,
            "raw_json": json.dumps(bar, default=str, ensure_ascii=False),
        }

    def read(self, kind: CrawlKind, codes: list[str]) -> list[dict]:
        if kind != CrawlKind.QUOTES:
            return []
        rows = self._read_by_column(self.storage, GOLD_PRICE_BOARD_TABLE, "code", codes)
        return _preferred_gold_rows(rows)

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


#: Floor for a missing ``crawled_at``. Not ``datetime.min``: comparing a
#: ``pd.Timestamp`` against year 1 raises ``OutOfBoundsDatetime`` (outside the
#: nanosecond range).
_EPOCH = datetime(1970, 1, 1)


def _gold_rank(row: dict) -> tuple[datetime, int]:
    """Sort key for picking one board row per code: freshest, then authority."""
    crawled = row.get("crawled_at")
    if crawled is None or crawled != crawled:  # None or NaT
        crawled = _EPOCH
    source = row.get("source")
    try:
        priority = BOARD_SOURCE_PRIORITY.index(source)
    except ValueError:
        # An unrecognised feed ranks last rather than blowing up the read.
        priority = len(BOARD_SOURCE_PRIORITY)
    return (crawled, -priority)


def _preferred_gold_rows(rows: list[dict]) -> list[dict]:
    """Collapse a ``(code, source)`` board to one row per code.

    The board deliberately keeps SJC-999 and Mihong-999 side by side, but a
    portfolio holding of "999" is one position and must show one price.
    Freshest wins — that is what keeps mihong acting as the SJC fallback now
    that it no longer overwrites SJC's row. Ties (the normal case: one crawl
    stamps every row with the same instant) go to the higher-authority source.
    """
    best: dict[str, dict] = {}
    for row in rows:
        code = row.get("code")
        current = best.get(code)
        if current is None or _gold_rank(row) > _gold_rank(current):
            best[code] = row
    return list(best.values())


def build_providers(
    storage: DuckDBStorage,
    *,
    data_source: str = "VCI",
    decision_source: str = "VCI",
    mihong_token: str | None = None,
) -> dict[AssetType, AssetProvider]:
    """Construct the provider registry (COIN deferred — no provider yet).

    ``data_source`` backs quotes + catalog (settings default = KBS in prod);
    ``decision_source`` backs news/events/ratios and defaults to VCI, which
    serves those kinds richly (KBS returns news≈1/events=0 live).
    """
    return {
        AssetType.STOCK: StockAssetProvider(
            storage,
            StockMarketSource(source=data_source),
            decision_market=StockMarketSource(source=decision_source),
        ),
        AssetType.GOLD: GoldAssetProvider(storage, xsrf_token=mihong_token),
    }
