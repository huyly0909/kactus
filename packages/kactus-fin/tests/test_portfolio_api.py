"""Tests for the kactus-fin portfolio API.

In-memory SQLite (OLTP) + tmp-file DuckDB (OLAP) + a fake market source (no
network).  ASGITransport does not run lifespan, so the portfolio runtime is
built directly in the fixture.
"""

from __future__ import annotations

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.events import dispatch_event
from kactus_common.portfolio.const import AssetType, CrawlKind, CrawlTrigger
from kactus_common.portfolio.events import MarketDataRefreshedPayload
from kactus_common.portfolio.service import CrawlRunService, SupportedAssetService
from kactus_common.sse.broker import get_sse_broker
from kactus_common.user import auth as auth_mod
from kactus_common.user.model import User
from kactus_data.portfolio.provider import StockAssetProvider
from kactus_data.sources.stock.market import StockMarketSource
from kactus_data.storage.duckdb import DuckDBStorage

TEST_DB_URL = "sqlite+aiosqlite://"


class FakeMarket(StockMarketSource):
    def _raw_price_board(self, codes):
        return pd.DataFrame(
            [
                {"symbol": c, "match_price": 25.5, "ref_price": 25.0,
                 "ceiling": 26.0, "floor": 24.0, "accumulated_volume": 500}
                for c in codes
            ]
        )

    def _raw_news(self, code):
        return pd.DataFrame(
            [{"id": f"{code}-1", "title": "Báo cáo quý", "public_date": "2026-06-17", "url": "u"}]
        )

    def _raw_events(self, code):
        return pd.DataFrame(
            [{"id": f"{code}-e", "event_title": "ĐHCĐ", "event_date": "2026-06-17"}]
        )

    def _raw_all_symbols(self):
        return pd.DataFrame([{"symbol": "FPT", "organ_name": "FPT Corp"}])

    def _raw_group(self, group):
        return ["FPT"]


@pytest_asyncio.fixture
async def db():
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()


@pytest_asyncio.fixture
async def app(db, tmp_path):
    from kactus_common.config import clear_settings, register_settings
    from kactus_fin.app import create_app
    from kactus_fin.config import Settings
    from kactus_fin.portfolio.runtime import PortfolioRuntime, set_runtime
    from kactus_fin.portfolio.sse import register_sse_handler
    from kactus_fin.portfolio.symbol_provider import FinSymbolProvider

    register_settings(
        Settings(enable_portfolio_scheduler=False, db_path=str(tmp_path / "t.duckdb"))
    )
    session_mod._db = db
    auth_mod._auth = None

    storage = DuckDBStorage(str(tmp_path / "t.duckdb"))
    # FakeMarket also backs decision_market so news/events don't hit the network.
    providers = {
        AssetType.STOCK: StockAssetProvider(storage, FakeMarket(), FakeMarket())
    }
    register_sse_handler()
    set_runtime(
        PortfolioRuntime(
            db=db,
            providers=providers,
            storage=storage,
            symbol_provider=FinSymbolProvider(db),
            scheduler=None,
        )
    )

    _app = create_app()
    yield _app

    set_runtime(None)
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


async def _seed_catalog(db, *codes):
    async with db.get_session() as session:
        await SupportedAssetService.upsert_many(
            session,
            asset_type=AssetType.STOCK,
            entries=[{"code": c, "name": c, "tags": ["VN30"]} for c in codes],
        )


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_requires_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/portfolios")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_portfolio_crud_and_items(client, db):
    await _seed_catalog(db, "FPT")

    # Create
    resp = await client.post("/api/portfolios", json={"name": "My WL"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0"
    pid = body["data"]["id"]

    # List
    resp = await client.get("/api/portfolios")
    assert resp.json()["data"]["total"] == 1

    # Add item
    resp = await client.post(
        f"/api/portfolios/{pid}/items", json={"asset_type": "STOCK", "code": "fpt"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["code"] == "FPT"

    # Detail shows the item
    resp = await client.get(f"/api/portfolios/{pid}")
    items = resp.json()["data"]["items"]
    assert [i["code"] for i in items] == ["FPT"]

    # Remove item
    resp = await client.request(
        "DELETE", f"/api/portfolios/{pid}/items", params={"code": "FPT", "asset_type": "STOCK"}
    )
    assert resp.status_code == 200

    # Delete portfolio
    resp = await client.delete(f"/api/portfolios/{pid}")
    assert resp.status_code == 200
    resp = await client.get("/api/portfolios")
    assert resp.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_add_item_uncatalogued_is_404(client):
    pid = (await client.post("/api/portfolios", json={"name": "WL"})).json()["data"]["id"]
    resp = await client.post(
        f"/api/portfolios/{pid}/items", json={"asset_type": "STOCK", "code": "NOPE"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_quotes_read_after_crawl(client, db):
    from kactus_fin.portfolio.runtime import get_runtime

    await _seed_catalog(db, "FPT")
    pid = (await client.post("/api/portfolios", json={"name": "WL"})).json()["data"]["id"]
    await client.post(
        f"/api/portfolios/{pid}/items", json={"asset_type": "STOCK", "code": "FPT"}
    )

    # Populate DuckDB via the (fake) provider, then read through the API.
    get_runtime().providers[AssetType.STOCK].crawl(CrawlKind.QUOTES, ["FPT"])

    resp = await client.get(f"/api/portfolios/{pid}/quotes")
    assert resp.status_code == 200
    quotes = resp.json()["data"]
    assert len(quotes) == 1
    assert quotes[0]["code"] == "FPT"
    # FancyFloat serialises to string in JSON.
    assert quotes[0]["match_price"] == "25.5"


@pytest.mark.asyncio
async def test_catalog_search(client, db):
    await _seed_catalog(db, "FPT", "VCB")
    resp = await client.get("/api/assets/supported", params={"q": "FP"})
    assert resp.status_code == 200
    codes = {a["code"] for a in resp.json()["data"]["items"]}
    assert codes == {"FPT"}


@pytest.mark.asyncio
async def test_manual_refresh_dedup(client, db):
    await _seed_catalog(db, "FPT")
    pid = (await client.post("/api/portfolios", json={"name": "WL"})).json()["data"]["id"]
    await client.post(
        f"/api/portfolios/{pid}/items", json={"asset_type": "STOCK", "code": "FPT"}
    )
    # Pre-existing in-flight quotes crawl → refresh must be skipped.
    async with db.get_session() as session:
        await CrawlRunService.start(
            session, asset_type=AssetType.STOCK, kind=CrawlKind.QUOTES
        )
    resp = await client.post(f"/api/portfolios/{pid}/refresh")
    assert resp.status_code == 200
    assert resp.json()["data"]["skipped"] is True


@pytest.mark.asyncio
async def test_sse_handler_bridges_event_to_broker(app):
    # `app` fixture has called register_sse_handler().
    broker = get_sse_broker()
    queue = await broker.subscribe()
    try:
        await MarketDataRefreshedPayload(
            asset_type="STOCK", kind="quotes", codes=["FPT"]
        ).dispatch(background=False)
        msg = await queue.get()
    finally:
        broker.unsubscribe(queue)
    assert msg["kind"] == "quotes"
    assert msg["codes"] == ["FPT"]


@pytest.mark.asyncio
async def test_news_and_asset_detail_reads(client, db):
    from kactus_fin.portfolio.runtime import get_runtime

    await _seed_catalog(db, "FPT")
    pid = (await client.post("/api/portfolios", json={"name": "WL"})).json()["data"]["id"]
    await client.post(
        f"/api/portfolios/{pid}/items", json={"asset_type": "STOCK", "code": "FPT"}
    )
    provider = get_runtime().providers[AssetType.STOCK]
    provider.crawl(CrawlKind.NEWS, ["FPT"])
    provider.crawl(CrawlKind.EVENTS, ["FPT"])

    news = (await client.get(f"/api/portfolios/{pid}/news")).json()["data"]
    assert news and news[0]["symbol"] == "FPT"

    detail = (await client.get("/api/assets/STOCK/FPT/events")).json()["data"]
    assert detail and detail[0]["symbol"] == "FPT"
    assert detail[0]["data"]["title"] == "ĐHCĐ"


@pytest.mark.asyncio
async def test_update_and_empty_refresh(client):
    pid = (await client.post("/api/portfolios", json={"name": "Old"})).json()["data"]["id"]
    resp = await client.put(f"/api/portfolios/{pid}", json={"name": "New", "description": "d"})
    assert resp.json()["data"]["name"] == "New"

    # Empty portfolio → refresh is a no-op, reported as skipped.
    resp = await client.post(f"/api/portfolios/{pid}/refresh")
    assert resp.json()["data"]["skipped"] is True


@pytest.mark.asyncio
async def test_fin_symbol_provider_union_plus_baseline(db):
    from kactus_fin.portfolio.symbol_provider import FinSymbolProvider

    async with db.get_session() as session:
        # FPT tagged VN30 (baseline), VCB plain — both crawlable.
        await SupportedAssetService.upsert_many(
            session, asset_type=AssetType.STOCK,
            entries=[{"code": "FPT", "tags": ["VN30"]}, {"code": "VCB", "tags": []}],
        )
        from kactus_common.portfolio.service import PortfolioService

        p = await PortfolioService.create(session, name="P", owner_id=1)
        await PortfolioService.add_item(
            session, portfolio_id=p.id, asset_type=AssetType.STOCK, code="VCB"
        )

    codes = await FinSymbolProvider(db).get_codes_by_type()
    # VCB from the watchlist union; FPT from the VN30 baseline.
    assert set(codes[str(AssetType.STOCK)]) == {"FPT", "VCB"}


@pytest_asyncio.fixture
async def admin_client(app, db):
    async with db.get_session() as session:
        admin = User.init(
            email="admin@kactus.io", username="admin", password_hash="Admin123!",
            name="Admin", status="active", is_superuser=True,
        )
        session.add(admin)
        await session.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        login = await c.post(
            "/api/auth/login", json={"email": "admin@kactus.io", "password": "Admin123!"}
        )
        c.cookies.update(dict(login.cookies))
        yield c


@pytest.mark.asyncio
async def test_admin_endpoints(admin_client, db):
    # list all portfolios
    assert (await admin_client.get("/api/admin/portfolios")).status_code == 200
    # crawl runs
    assert (await admin_client.get("/api/admin/portfolios/crawl-runs")).status_code == 200
    # crawl status (scheduler off in tests)
    status = (await admin_client.get("/api/admin/portfolios/crawl-status")).json()["data"]
    assert status["scheduler_running"] is False
    # trigger crawl (background task scheduled)
    assert (await admin_client.post("/api/admin/portfolios/crawl/run-now")).json()["data"]["skipped"] is False
    # catalog sync
    assert (await admin_client.post("/api/admin/portfolios/catalog/sync")).status_code == 200


@pytest.mark.asyncio
async def test_admin_requires_superuser(client):
    # A normal (non-superuser) session is rejected from admin routes.
    resp = await client.get("/api/admin/portfolios")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_build_runtime_helper(db, tmp_path):
    """Covers the lifespan runtime builder (scheduler disabled, no network)."""
    from kactus_common.config import clear_settings, register_settings
    from kactus_fin.app import _build_portfolio_runtime, _shutdown_portfolio_runtime
    from kactus_fin.config import Settings

    register_settings(
        Settings(enable_portfolio_scheduler=False, db_path=str(tmp_path / "rt.duckdb"))
    )
    session_mod._db = db
    try:
        runtime = _build_portfolio_runtime(Settings(enable_portfolio_scheduler=False))
        assert runtime.scheduler is None
        assert AssetType.STOCK in runtime.providers
    finally:
        _shutdown_portfolio_runtime(runtime)
        session_mod._db = None
        clear_settings()
