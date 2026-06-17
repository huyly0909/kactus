"""Tests for the portfolio crawl layer.

Uses a fake :class:`StockMarketSource` (overriding only the raw vnstock seams),
a tmp-file DuckDB, and in-memory SQLite for crawl-run state — no network.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
import pytest_asyncio
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.events import register_handler
from kactus_common.portfolio.const import (
    AssetType,
    CrawlKind,
    CrawlStatus,
    CrawlTrigger,
)
from kactus_common.portfolio.events import MarketEventName
from kactus_common.portfolio.service import CrawlRunService
from kactus_data.jobs.crawl import run_crawl
from kactus_data.portfolio.provider import StockAssetProvider
from kactus_data.sources.stock.market import StockMarketSource
from kactus_data.storage.duckdb import DuckDBStorage


class FakeMarket(StockMarketSource):
    """vnstock-free market source: only the raw seams are overridden."""

    def _raw_price_board(self, codes):
        return pd.DataFrame(
            [
                {
                    "symbol": c,
                    "match_price": 10.0,
                    "ref_price": 9.5,
                    "ceiling": 11.0,
                    "floor": 9.0,
                    "accumulated_volume": 1000,
                }
                for c in codes
            ]
        )

    def _raw_news(self, code):
        # Vietnamese text + apostrophe + newline → exercises register-insert safety.
        return pd.DataFrame(
            [
                {
                    "id": f"{code}-1",
                    "title": "Lợi nhuận 'tăng' mạnh\nquý 4 — báo cáo",
                    "public_date": "2026-06-17",
                    "url": "https://example.com/news/1",
                }
            ]
        )


@pytest_asyncio.fixture
async def db():
    manager = DatabaseSessionManager(database_url="sqlite+aiosqlite://")
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    await manager.close()


@pytest.fixture
def storage(tmp_path):
    return DuckDBStorage(str(tmp_path / "test.duckdb"))


def test_provider_crawl_quotes_roundtrip(storage):
    provider = StockAssetProvider(storage, FakeMarket(source="VCI"))
    n = provider.crawl(CrawlKind.QUOTES, ["FPT", "VCB"])
    assert n == 2
    rows = provider.read(CrawlKind.QUOTES, ["FPT"])
    assert len(rows) == 1
    assert rows[0]["symbol"] == "FPT"
    assert rows[0]["match_price"] == 10.0
    assert rows[0]["source"] == "VCI"


def test_provider_crawl_news_is_text_safe(storage):
    """Vietnamese news with quotes/newlines round-trips intact (register insert)."""
    provider = StockAssetProvider(storage, FakeMarket())
    n = provider.crawl(CrawlKind.NEWS, ["FPT"])
    assert n == 1
    rows = provider.read(CrawlKind.NEWS, ["FPT"])
    assert "tăng" in rows[0]["title"]
    assert "\n" in rows[0]["title"]
    # raw_json is valid JSON and preserves the original payload.
    raw = json.loads(rows[0]["raw_json"])
    assert raw["id"] == "FPT-1"


def test_provider_crawl_empty_codes(storage):
    provider = StockAssetProvider(storage, FakeMarket())
    assert provider.crawl(CrawlKind.QUOTES, []) == 0


@pytest.mark.asyncio
async def test_run_crawl_records_run_and_emits_event(db, storage):
    received = []

    @register_handler(MarketEventName.data_refreshed)
    async def _handler(*, event_name, payload):
        received.append(payload)

    provider = StockAssetProvider(storage, FakeMarket())
    providers = {AssetType.STOCK: provider}

    run_ids = await run_crawl(
        db=db,
        providers=providers,
        kind=CrawlKind.QUOTES,
        codes_by_type={"STOCK": ["FPT", "VCB"]},
        trigger=CrawlTrigger.MANUAL,
    )
    assert len(run_ids) == 1

    # SSE nudge emitted with the crawled codes.
    assert received, "expected a data_refreshed event"
    assert received[-1].kind == "quotes"
    assert set(received[-1].codes) == {"FPT", "VCB"}

    # Crawl run recorded as SUCCESS with the row count.
    async with db.get_session() as session:
        recent = await CrawlRunService.list_recent(session)
    assert recent[0].status == str(CrawlStatus.SUCCESS)
    assert recent[0].rows_written == 2


@pytest.mark.asyncio
async def test_run_crawl_dedup_skips_inflight(db, storage):
    provider = StockAssetProvider(storage, FakeMarket())
    providers = {AssetType.STOCK: provider}

    # Pre-existing in-flight run for (STOCK, quotes).
    async with db.get_session() as session:
        await CrawlRunService.start(
            session, asset_type=AssetType.STOCK, kind=CrawlKind.QUOTES
        )

    run_ids = await run_crawl(
        db=db,
        providers=providers,
        kind=CrawlKind.QUOTES,
        codes_by_type={"STOCK": ["FPT"]},
        trigger=CrawlTrigger.MANUAL,
        dedup=True,
    )
    assert run_ids == []  # deduped — no new run started
