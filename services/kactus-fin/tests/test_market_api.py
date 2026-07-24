"""Tests for the kactus-fin market API (gold / stock / finance reads).

In-memory SQLite (OLTP) for auth + a tmp-file DuckDB (OLAP) seeded directly with
ETL-shaped rows.  ASGITransport does not run lifespan, so the OLAP storage is
published by the fixture instead of the app factory.
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
from kactus_common.user import auth as auth_mod
from kactus_common.user.model import User
from kactus_data.sources.company.tables import COMPANY_TABLE
from kactus_data.sources.finance.tables import FINANCE_TABLE
from kactus_data.sources.gold.portfolio_tables import GOLD_PRICE_BOARD_TABLE
from kactus_data.sources.stock.portfolio_tables import (
    STOCK_NEWS_TABLE,
    STOCK_PRICE_BOARD_TABLE,
)
from kactus_data.sources.stock.tables import STOCK_LISTING_TABLE, STOCK_OHLCV_TABLE
from kactus_data.storage.duckdb import DuckDBStorage

TEST_DB_URL = "sqlite+aiosqlite://"


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
    from kactus_fin.app import create_app
    from kactus_fin.config import Settings
    from kactus_fin.olap import set_olap_storage

    register_settings(
        Settings(
            enable_portfolio_scheduler=False, db_path=str(tmp_path / "market.duckdb")
        )
    )
    session_mod._db = db
    auth_mod._auth = None
    set_olap_storage(storage)

    yield create_app()

    set_olap_storage(None)
    session_mod._db = None
    auth_mod._auth = None
    clear_settings()


@pytest_asyncio.fixture
async def seed_user(db) -> User:
    async with db.get_session() as session:
        user = User.init(
            email="trader@kactus.io",
            username="trader",
            password_hash="Test123!",
            name="Trader",
            status="active",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client(app, seed_user):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        login = await c.post(
            "/api/auth/login",
            json={"email": "trader@kactus.io", "password": "Test123!"},
        )
        assert login.status_code == 200
        c.cookies.update(dict(login.cookies))
        yield c


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_requires_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/market/gold")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_gold_board_and_filter(client):
    resp = await client.get("/api/market/gold")
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert {r["code"] for r in rows} == {"999", "SJC", "XAU"}

    sjc = next(r for r in rows if r["code"] == "SJC")
    # spread is derived, not stored
    assert float(sjc["spread"]) == pytest.approx(2_000_000.0)

    filtered = await client.get("/api/market/gold", params={"code": "SJC"})
    assert [r["code"] for r in filtered.json()["data"]] == ["SJC"]


@pytest.mark.asyncio
async def test_gold_prices_are_exact_and_unit_tagged(client):
    """Money survives the round trip as an exact decimal string, not a float.

    Domestic gold (~1.2e8 VND) is past float32's exact range and lands on
    binary fractions in float64, so the board stores DECIMAL and the API
    serialises it as a string.  ``unit`` is what tells VND/lượng apart from
    the USD/oz world price on the same board.
    """
    rows = (await client.get("/api/market/gold")).json()["data"]
    by_code = {r["code"]: r for r in rows}

    assert by_code["SJC"]["buy_price"] == "121000000"
    assert by_code["SJC"]["spread"] == "2000000"
    assert by_code["SJC"]["unit"] == "VND/luong"

    # World gold shares the board but is quoted per troy ounce in USD.
    assert by_code["XAU"]["unit"] == "USD/oz"
    assert by_code["XAU"]["buy_price"] == "4037.6999"


@pytest.mark.asyncio
async def test_stock_search_by_symbol_and_name(client):
    all_rows = await client.get("/api/market/stocks")
    assert [r["symbol"] for r in all_rows.json()["data"]] == ["FPT", "VNM"]

    by_symbol = await client.get("/api/market/stocks", params={"q": "fpt"})
    assert [r["symbol"] for r in by_symbol.json()["data"]] == ["FPT"]

    by_name = await client.get("/api/market/stocks", params={"q": "vinamilk"})
    assert [r["symbol"] for r in by_name.json()["data"]] == ["VNM"]


@pytest.mark.asyncio
async def test_stock_detail_merges_company_and_quote(client):
    resp = await client.get("/api/market/stocks/fpt")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "FPT"
    assert data["organ_name"] == "FPT Corp"
    assert data["company"]["industry"] == "Technology"
    # change/change_pct derived from match vs ref
    assert float(data["quote"]["change"]) == pytest.approx(10.0)
    assert float(data["quote"]["change_pct"]) == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_unknown_symbol_is_404(client):
    resp = await client.get("/api/market/stocks/NOPE")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_quotes_board(client):
    resp = await client.get("/api/market/stocks/quotes", params={"symbol": "fpt"})
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) == 1 and rows[0]["symbol"] == "FPT"


@pytest.mark.asyncio
async def test_ohlcv_is_ascending_and_capped(client):
    resp = await client.get("/api/market/stocks/FPT/ohlcv")
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert [r["time"][:10] for r in rows] == ["2026-07-20", "2026-07-21", "2026-07-22"]

    # limit keeps the *newest* rows, still returned oldest → newest
    capped = await client.get("/api/market/stocks/FPT/ohlcv", params={"limit": 2})
    assert [r["time"][:10] for r in capped.json()["data"]] == [
        "2026-07-21",
        "2026-07-22",
    ]


@pytest.mark.asyncio
async def test_ohlcv_date_range_and_unknown_interval(client):
    ranged = await client.get(
        "/api/market/stocks/FPT/ohlcv",
        params={"start": "2026-07-21", "end": "2026-07-21"},
    )
    assert [r["time"][:10] for r in ranged.json()["data"]] == ["2026-07-21"]

    # an interval that was never crawled is empty, not an error
    empty = await client.get("/api/market/stocks/FPT/ohlcv", params={"interval": "1W"})
    assert empty.json()["data"] == []

    # an interval outside the enum is rejected up front
    bad = await client.get("/api/market/stocks/FPT/ohlcv", params={"interval": "3Y"})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_news(client):
    resp = await client.get("/api/market/stocks/FPT/news")
    rows = resp.json()["data"]
    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.test/n1"


@pytest.mark.asyncio
async def test_finance_reports_newest_first(client):
    resp = await client.get(
        "/api/market/stocks/FPT/finance",
        params={"report_type": "income_statement", "period": "quarter"},
    )
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert [r["year"] for r in rows] == ["2026", "2025"]
    # data_json is exploded back into a dict
    assert rows[0]["data"]["revenue"] == 2026 * 1000

    # a report type with no crawled rows is empty, not an error
    empty = await client.get(
        "/api/market/stocks/FPT/finance", params={"report_type": "cash_flow"}
    )
    assert empty.json()["data"] == []


@pytest.mark.asyncio
async def test_missing_tables_return_empty(client, tmp_path):
    """A DuckDB file with no ETL tables yet reads as 'no data', not a 500."""
    from kactus_fin.olap import set_olap_storage

    set_olap_storage(DuckDBStorage(str(tmp_path / "empty.duckdb")))
    resp = await client.get("/api/market/gold")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_olap_storage_not_initialised():
    from kactus_common.exceptions import InternalError
    from kactus_fin.olap import get_olap_storage, set_olap_storage

    set_olap_storage(None)
    with pytest.raises(InternalError):
        get_olap_storage()
