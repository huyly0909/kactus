"""Tests for the kactus-fin portfolio API.

In-memory SQLite for the OLTP side — portfolios, items and the crawl audit are
still this service's data. Market rows are not: they come from the fake data
plane in ``conftest.py``, which is where the DuckDB used to be.

``ASGITransport`` does not run lifespan, so the SSE handler is registered by the
fixture.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.portfolio.const import AssetType, CrawlKind
from kactus_common.portfolio.events import MarketDataRefreshedPayload
from kactus_common.portfolio.schema import MarketRowSchema
from kactus_common.portfolio.service import CrawlRunService, SupportedAssetService
from kactus_common.sse.broker import get_sse_broker
from kactus_common.user import auth as auth_mod
from kactus_common.user.model import User

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


@pytest_asyncio.fixture
async def app(db):
    from kactus_common.config import clear_settings, register_settings
    from kactus_common.sse.market import register_sse_handler, reset_sse_handler
    from kactus_fin.app import create_app
    from kactus_fin.config import Settings

    register_settings(Settings(internal_service_token="test-token"))
    session_mod._db = db
    auth_mod._auth = None
    register_sse_handler()

    yield create_app()

    reset_sse_handler()
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


async def _make_portfolio(client, db, *codes):
    await _seed_catalog(db, *codes)
    pid = (await client.post("/api/portfolios", json={"name": "WL"})).json()["data"][
        "id"
    ]
    for code in codes:
        await client.post(
            f"/api/portfolios/{pid}/items",
            json={"asset_type": "STOCK", "code": code},
        )
    return pid


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
        "DELETE",
        f"/api/portfolios/{pid}/items",
        params={"code": "FPT", "asset_type": "STOCK"},
    )
    assert resp.status_code == 200

    # Delete portfolio
    resp = await client.delete(f"/api/portfolios/{pid}")
    assert resp.status_code == 200
    resp = await client.get("/api/portfolios")
    assert resp.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_add_item_uncatalogued_is_404(client):
    pid = (await client.post("/api/portfolios", json={"name": "WL"})).json()["data"][
        "id"
    ]
    resp = await client.post(
        f"/api/portfolios/{pid}/items", json={"asset_type": "STOCK", "code": "NOPE"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_quotes_projects_data_plane_rows(client, db, data_plane):
    """The portfolio's own codes go out; the rows come back projected.

    The projection (opaque ``data`` dict → ``MarketQuoteSchema``) is what this
    service still owns after the split, so it is what is asserted here.
    """
    pid = await _make_portfolio(client, db, "FPT")
    data_plane.asset_rows[("STOCK", "quotes")] = [
        MarketRowSchema(
            symbol="FPT",
            data={
                "match_price": 25.5,
                "ref_price": 25.0,
                "accumulated_volume": 500,
                "source": "KBS",
            },
        )
    ]

    resp = await client.get(f"/api/portfolios/{pid}/quotes")
    assert resp.status_code == 200
    quotes = resp.json()["data"]
    assert len(quotes) == 1
    assert quotes[0]["code"] == "FPT"
    # FancyFloat serialises to string in JSON.
    assert quotes[0]["match_price"] == "25.5"
    # `accumulated_volume` is renamed to `volume` on the way out.
    assert quotes[0]["volume"] == "500.0"
    assert data_plane.last("assets")["code"] == ["FPT"]


@pytest.mark.asyncio
async def test_quotes_asks_only_for_the_types_the_portfolio_holds(
    client, db, data_plane
):
    """A stock-only watchlist must not trigger a gold read.

    Every asset type is a separate round trip now; asking for types the user
    does not hold is pure latency on the page that loads most often.
    """
    pid = await _make_portfolio(client, db, "FPT")
    await client.get(f"/api/portfolios/{pid}/quotes")
    asset_calls = [p for c, p in data_plane.calls if c == "assets"]
    assert [p["asset_type"] for p in asset_calls] == ["STOCK"]


@pytest.mark.asyncio
async def test_empty_portfolio_makes_no_data_plane_call(client, data_plane):
    pid = (await client.post("/api/portfolios", json={"name": "WL"})).json()["data"][
        "id"
    ]
    assert (await client.get(f"/api/portfolios/{pid}/quotes")).json()["data"] == []
    assert not [c for c, _ in data_plane.calls if c == "assets"]


@pytest.mark.asyncio
async def test_catalog_search(client, db):
    await _seed_catalog(db, "FPT", "VCB")
    resp = await client.get("/api/assets/supported", params={"q": "FP"})
    assert resp.status_code == 200
    codes = {a["code"] for a in resp.json()["data"]["items"]}
    assert codes == {"FPT"}


@pytest.mark.asyncio
async def test_manual_refresh_forwards_to_the_data_plane(client, db, data_plane):
    pid = await _make_portfolio(client, db, "FPT")
    resp = await client.post(f"/api/portfolios/{pid}/refresh")
    assert resp.status_code == 200
    assert resp.json()["data"]["skipped"] is False

    sent = data_plane.last("crawl")
    assert sent["kind"] == "quotes"
    assert sent["codes_by_type"] == {"STOCK": ["FPT"]}
    assert sent["portfolio_id"] == str(pid)
    assert sent["trigger"] == "manual"
    assert sent["dedup"] is True


@pytest.mark.asyncio
async def test_manual_refresh_dedup_stops_at_the_control_plane(client, db, data_plane):
    """The in-flight guard runs here, against the shared Postgres.

    Both planes see the same ``CrawlRun`` table, so the check could live on
    either side — doing it here means a duplicate refresh costs no round trip
    and the user gets the real reason back, not a generic "scheduled".
    """
    pid = await _make_portfolio(client, db, "FPT")
    async with db.get_session() as session:
        await CrawlRunService.start(
            session, asset_type=AssetType.STOCK, kind=CrawlKind.QUOTES
        )

    resp = await client.post(f"/api/portfolios/{pid}/refresh")
    assert resp.json()["data"]["skipped"] is True
    assert not [c for c, _ in data_plane.calls if c == "crawl"]


@pytest.mark.asyncio
async def test_refresh_reports_a_dead_data_plane_instead_of_lying(client, db):
    """A "Refresh scheduled" that never happened is the worse failure.

    The call is awaited rather than fired into a local BackgroundTasks
    precisely so this surfaces.
    """
    import httpx
    from kactus_fin import data_client

    pid = await _make_portfolio(client, db, "FPT")

    async def boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    original = data_client.get_client().request
    data_client.get_client().request = boom
    try:
        resp = await client.post(f"/api/portfolios/{pid}/refresh")
    finally:
        data_client.get_client().request = original

    assert resp.status_code == 502


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
async def test_news_and_asset_detail_reads(client, db, data_plane):
    pid = await _make_portfolio(client, db, "FPT")
    data_plane.asset_rows[("STOCK", "news")] = [
        MarketRowSchema(
            symbol="FPT",
            data={
                "symbol": "FPT",
                "news_id": "FPT-1",
                "title": "Báo cáo quý",
                "published_at": "2026-06-17",
                "url": "u",
            },
        )
    ]
    data_plane.asset_rows[("STOCK", "events")] = [
        MarketRowSchema(symbol="FPT", data={"title": "ĐHCĐ"})
    ]

    news = (await client.get(f"/api/portfolios/{pid}/news")).json()["data"]
    assert news and news[0]["symbol"] == "FPT"

    detail = (await client.get("/api/assets/STOCK/FPT/events")).json()["data"]
    assert detail and detail[0]["symbol"] == "FPT"
    assert detail[0]["data"]["title"] == "ĐHCĐ"


@pytest.mark.asyncio
async def test_asset_detail_upper_cases_the_code(client, data_plane):
    await client.get("/api/assets/STOCK/fpt/events")
    assert data_plane.last("assets")["code"] == ["FPT"]


@pytest.mark.asyncio
async def test_update_and_empty_refresh(client):
    pid = (await client.post("/api/portfolios", json={"name": "Old"})).json()["data"][
        "id"
    ]
    resp = await client.put(
        f"/api/portfolios/{pid}", json={"name": "New", "description": "d"}
    )
    assert resp.json()["data"]["name"] == "New"

    # Empty portfolio → refresh is a no-op, reported as skipped.
    resp = await client.post(f"/api/portfolios/{pid}/refresh")
    assert resp.json()["data"]["skipped"] is True


@pytest_asyncio.fixture
async def admin_client(app, db):
    async with db.get_session() as session:
        admin = User.init(
            email="admin@kactus.io",
            username="admin",
            password_hash="Admin123!",
            name="Admin",
            status="active",
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        login = await c.post(
            "/api/auth/login",
            json={"email": "admin@kactus.io", "password": "Admin123!"},
        )
        c.cookies.update(dict(login.cookies))
        yield c


@pytest.mark.asyncio
async def test_admin_endpoints(admin_client, db, data_plane):
    # list all portfolios
    assert (await admin_client.get("/api/admin/portfolios")).status_code == 200
    # crawl runs — still read from this service's Postgres
    assert (
        await admin_client.get("/api/admin/portfolios/crawl-runs")
    ).status_code == 200
    # crawl status is now the data plane's answer, forwarded
    status = (await admin_client.get("/api/admin/portfolios/crawl-status")).json()[
        "data"
    ]
    assert status["scheduler_running"] is True
    assert [j["id"] for j in status["jobs"]] == ["crawl_quotes"]
    # trigger crawl
    assert (await admin_client.post("/api/admin/portfolios/crawl/run-now")).json()[
        "data"
    ]["skipped"] is False
    assert data_plane.last("crawl")["kind"] == "quotes"
    # catalog sync
    assert (
        await admin_client.post("/api/admin/portfolios/catalog/sync")
    ).status_code == 200
    assert data_plane.last("catalog_sync") == {}


@pytest.mark.asyncio
async def test_admin_requires_superuser(client):
    # A normal (non-superuser) session is rejected from admin routes.
    resp = await client.get("/api/admin/portfolios")
    assert resp.status_code in (401, 403)
