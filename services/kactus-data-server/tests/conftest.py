"""Fixtures for the data plane: in-memory OLTP + a tmp-file DuckDB seeded with
ETL-shaped rows.

This is where the DuckDB-backed market tests live now. They used to sit in
kactus-fin's suite because kactus-fin held the storage handle; after the split
it holds none, and a test there could not seed one without re-introducing the
dependency the whole phase exists to remove.

``ASGITransport`` does not run lifespan, so the fixtures publish the runtime
directly instead of going through ``build_runtime`` (which would authenticate
against vnstock and start a scheduler).
"""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.portfolio.const import AssetType
from kactus_data.portfolio.provider import StockAssetProvider
from kactus_data.sources.company.tables import COMPANY_TABLE
from kactus_data.sources.finance.tables import FINANCE_TABLE
from kactus_data.sources.gold.portfolio_tables import GOLD_PRICE_BOARD_TABLE
from kactus_data.sources.stock.market import StockMarketSource
from kactus_data.sources.stock.portfolio_tables import (
    STOCK_NEWS_TABLE,
    STOCK_PRICE_BOARD_TABLE,
)
from kactus_data.sources.stock.tables import STOCK_LISTING_TABLE, STOCK_OHLCV_TABLE
from kactus_data.storage.duckdb import DuckDBStorage

TEST_DB_URL = "sqlite+aiosqlite://"
SERVICE_TOKEN = "test-service-token"


class FakeMarket(StockMarketSource):
    """A StockMarketSource that answers from memory instead of vnstock."""

    def _raw_price_board(self, codes):
        return pd.DataFrame(
            [
                {
                    "symbol": c,
                    "match_price": 25.5,
                    "ref_price": 25.0,
                    "ceiling": 26.0,
                    "floor": 24.0,
                    "accumulated_volume": 500,
                }
                for c in codes
            ]
        )

    def _raw_news(self, code):
        return pd.DataFrame(
            [
                {
                    "id": f"{code}-1",
                    "title": "Báo cáo quý",
                    "public_date": "2026-06-17",
                    "url": "u",
                }
            ]
        )

    def _raw_events(self, code):
        return pd.DataFrame(
            [{"id": f"{code}-e", "event_title": "ĐHCĐ", "event_date": "2026-06-17"}]
        )

    def _raw_all_symbols(self):
        return pd.DataFrame([{"symbol": "FPT", "organ_name": "FPT Corp"}])

    def _raw_group(self, group):
        return ["FPT"]


@pytest.fixture
def service_token() -> str:
    """The token the fixtures configure — a fixture, not an import.

    Test directories carry no ``__init__.py``, so ``from .conftest import ...``
    is not available to sibling modules.
    """
    return SERVICE_TOKEN


@pytest_asyncio.fixture
async def db():
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()


@pytest.fixture
def storage(tmp_path) -> DuckDBStorage:
    """A DuckDB file seeded with one row per market table."""
    store = DuckDBStorage(str(tmp_path / "market.duckdb"))
    now = datetime(2026, 7, 24, 9, 30)

    store.store(
        GOLD_PRICE_BOARD_TABLE,
        pd.DataFrame(
            [
                {
                    "code": "SJC",
                    "buy_price": 121_000_000.0,
                    "sell_price": 123_000_000.0,
                    "unit": "VND/luong",
                    "source": "sjc",
                    "crawled_at": now,
                    "raw_json": "{}",
                },
                {
                    "code": "999",
                    "buy_price": 118_000_000.0,
                    "sell_price": 119_500_000.0,
                    "unit": "VND/luong",
                    "source": "mihong",
                    "crawled_at": now,
                    "raw_json": "{}",
                },
                {
                    "code": "XAU",
                    "buy_price": 4037.6999,
                    "sell_price": 4037.6999,
                    "unit": "USD/oz",
                    "source": "yahoo",
                    "crawled_at": now,
                    "raw_json": "{}",
                },
            ]
        ),
    )
    store.store(
        STOCK_LISTING_TABLE,
        pd.DataFrame(
            [
                {
                    "symbol": "FPT",
                    "organ_name": "FPT Corp",
                    "source": "KBS",
                    "synced_at": now,
                },
                {
                    "symbol": "VNM",
                    "organ_name": "Vinamilk",
                    "source": "KBS",
                    "synced_at": now,
                },
            ]
        ),
    )
    store.store(
        COMPANY_TABLE,
        pd.DataFrame(
            [
                {
                    "symbol": "FPT",
                    "company_name": "FPT Corporation",
                    "short_name": "FPT",
                    "industry": "Technology",
                    "exchange": "HOSE",
                    "market_cap": 1.0e14,
                    "outstanding_shares": 1.4e9,
                    "overview_json": "{}",
                    "source": "KBS",
                    "synced_at": now,
                }
            ]
        ),
    )
    store.store(
        STOCK_PRICE_BOARD_TABLE,
        pd.DataFrame(
            [
                {
                    "symbol": "FPT",
                    "match_price": 110.0,
                    "ref_price": 100.0,
                    "ceiling": 107.0,
                    "floor": 93.0,
                    "accumulated_volume": 1_000_000.0,
                    "source": "KBS",
                    "crawled_at": now,
                    "raw_json": "{}",
                }
            ]
        ),
    )
    store.store(
        STOCK_OHLCV_TABLE,
        pd.DataFrame(
            [
                {
                    "symbol": "FPT",
                    "time": datetime(2026, 7, day, 15, 0),
                    "interval": "1D",
                    "open": 100.0 + day,
                    "high": 102.0 + day,
                    "low": 99.0 + day,
                    "close": 101.0 + day,
                    "volume": 1000.0 * day,
                    "source": "KBS",
                }
                for day in (20, 21, 22)
            ]
        ),
    )
    store.store(
        STOCK_NEWS_TABLE,
        pd.DataFrame(
            [
                {
                    "symbol": "FPT",
                    "news_id": "n1",
                    "title": "FPT ký hợp đồng mới",
                    "published_at": "2026-07-23",
                    "url": "https://example.test/n1",
                    "source": "KBS",
                    "crawled_at": now,
                    "raw_json": "{}",
                }
            ]
        ),
    )
    store.store(
        FINANCE_TABLE,
        pd.DataFrame(
            [
                {
                    "symbol": "FPT",
                    "period": "quarter",
                    "year": year,
                    "quarter": 2,
                    "report_type": "income_statement",
                    "data_json": json.dumps({"revenue": 1000 * year}),
                    "source": "KBS",
                    "synced_at": now,
                }
                for year in (2025, 2026)
            ]
        ),
    )
    return store


@pytest_asyncio.fixture
async def app(db, storage, tmp_path):
    from kactus_common.config import clear_settings, register_settings
    from kactus_data_server.app import create_app
    from kactus_data_server.config import Settings
    from kactus_data_server.runtime import DataRuntime, set_runtime
    from kactus_data_server.symbol_provider import WatchlistSymbolProvider

    register_settings(
        Settings(
            enable_portfolio_scheduler=False,
            db_path=str(tmp_path / "market.duckdb"),
            internal_service_token=SERVICE_TOKEN,
        )
    )
    session_mod._db = db

    providers = {
        AssetType.STOCK: StockAssetProvider(storage, FakeMarket(), FakeMarket())
    }
    set_runtime(
        DataRuntime(
            db=db,
            providers=providers,
            storage=storage,
            symbol_provider=WatchlistSymbolProvider(db),
            scheduler=None,
        )
    )

    yield create_app()

    set_runtime(None)
    session_mod._db = None
    clear_settings()


@pytest_asyncio.fixture
async def client(app):
    """A client that holds the service token — the normal caller."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-Service-Token": SERVICE_TOKEN},
    ) as c:
        yield c


@pytest_asyncio.fixture
async def anon_client(app):
    """A client with no token — stands in for anything else on the network."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
