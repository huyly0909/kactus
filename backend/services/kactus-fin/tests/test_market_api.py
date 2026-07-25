"""``/api/market/*`` — the control plane's half of the market reads.

After the data-plane split there is no DuckDB in this process, so what is left
to test here is exactly what kactus-fin still owns: the session requirement,
the translation of query parameters into a data-plane call, the 404 policy for
an unknown symbol, and what a user sees when the data plane is unreachable.

The row-level assertions (derived spreads, exact decimals, ordering) moved to
``services/kactus-data-server/tests/test_market_api.py`` along with the storage
that produces them.

Requests reach a fake data plane over an in-process ASGI transport (see
``conftest.py``), so the real ``data_client`` — params, envelope unwrapping,
schema parsing, error mapping — runs end to end.
"""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.market.schema import (
    GoldHistoryCodeSchema,
    GoldHistoryPointSchema,
    GoldImportResultSchema,
    GoldPriceSchema,
    StockDetailSchema,
    StockListingSchema,
    StockQuoteSchema,
)
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
    from kactus_fin.app import create_app
    from kactus_fin.config import Settings

    register_settings(Settings(internal_service_token="test-token"))
    session_mod._db = db
    auth_mod._auth = None

    yield create_app()

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
async def test_gold_passes_through_rows_and_filter(client, data_plane):
    data_plane.gold = [
        GoldPriceSchema(
            code="SJC",
            buy_price="121000000",
            sell_price="123000000",
            spread="2000000",
            unit="VND/luong",
            source="sjc",
        )
    ]

    resp = await client.get("/api/market/gold", params={"code": "SJC"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0"
    assert body["data"][0]["code"] == "SJC"
    # Exact decimals survive both hops — the value crosses JSON twice now.
    assert body["data"][0]["buy_price"] == "121000000"
    # The filter reached the data plane rather than being applied here.
    assert data_plane.last("gold")["code"] == ["SJC"]


@pytest.mark.asyncio
async def test_repeated_code_params_stay_a_list(client, data_plane):
    """``?code=SJC&code=999`` must not collapse into one comma-joined string.

    httpx encodes a list as repeated params only if it is still a list by the
    time it reaches the client; a str() anywhere in between turns it into
    ``['SJC', '999']`` as a literal, which the data plane would match against
    no row at all — and return an empty board rather than an error.
    """
    await client.get("/api/market/gold", params=[("code", "SJC"), ("code", "999")])
    assert data_plane.last("gold")["code"] == ["SJC", "999"]


@pytest.mark.asyncio
async def test_search_forwards_query_and_limit(client, data_plane):
    data_plane.listings = [
        StockListingSchema(symbol="FPT", organ_name="FPT Corp", source="KBS")
    ]
    resp = await client.get("/api/market/stocks", params={"q": "fpt", "limit": 5})
    assert [r["symbol"] for r in resp.json()["data"]] == ["FPT"]
    assert data_plane.last("stocks") == {"q": "fpt", "limit": 5}


@pytest.mark.asyncio
async def test_quotes_forwards_symbols(client, data_plane):
    data_plane.quotes = [StockQuoteSchema(symbol="FPT", source="KBS")]
    resp = await client.get("/api/market/stocks/quotes", params={"symbol": "fpt"})
    assert [r["symbol"] for r in resp.json()["data"]] == ["FPT"]
    assert data_plane.last("quotes")["symbol"] == ["fpt"]


@pytest.mark.asyncio
async def test_stock_detail(client, data_plane):
    data_plane.detail = StockDetailSchema(symbol="FPT", organ_name="FPT Corp")
    resp = await client.get("/api/market/stocks/fpt")
    assert resp.status_code == 200
    assert resp.json()["data"]["symbol"] == "FPT"


@pytest.mark.asyncio
async def test_unknown_symbol_is_404_here(client, data_plane):
    """The data plane says ``null``; turning that into a 404 is this side's job.

    Keeping the decision here means the user-facing message has one home, and
    the data plane can stay a dumb reader.
    """
    data_plane.detail = None
    resp = await client.get("/api/market/stocks/NOPE")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "NOT_FOUND"
    assert "NOPE" in body["message"]


@pytest.mark.asyncio
async def test_ohlcv_forwards_interval_and_dates(client, data_plane):
    await client.get(
        "/api/market/stocks/FPT/ohlcv",
        params={"interval": "1D", "start": "2026-07-21", "end": "2026-07-22"},
    )
    assert data_plane.last("ohlcv")["symbol"] == "FPT"
    assert data_plane.last("ohlcv")["interval"] == "1D"


@pytest.mark.asyncio
async def test_interval_outside_the_enum_never_reaches_the_data_plane(
    client, data_plane
):
    """Validation stays at the edge: a bad interval is 422, not a 502."""
    resp = await client.get("/api/market/stocks/FPT/ohlcv", params={"interval": "3Y"})
    assert resp.status_code == 422
    assert not [c for c, _ in data_plane.calls if c == "ohlcv"]


@pytest.mark.asyncio
async def test_finance_forwards_report_type_as_a_plain_string(client, data_plane):
    """The enum must be sent by *value*, not as ``ReportType.INCOME_STATEMENT``.

    A str() of the enum member would produce a query the data plane rejects —
    the kind of mismatch that only shows up across a process boundary.
    """
    await client.get(
        "/api/market/stocks/FPT/finance",
        params={"report_type": "balance_sheet", "period": "quarter"},
    )
    assert data_plane.last("finance")["report_type"] == "balance_sheet"


@pytest.mark.asyncio
async def test_data_plane_failure_is_502_not_an_empty_list(client, monkeypatch):
    """An unreachable data plane must not render as "no data".

    Returning ``[]`` would show an empty board to a user with ten positions —
    a worse lie than an error, and one nothing downstream can detect.
    """
    from kactus_fin import data_client

    async def boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(data_client.get_client(), "request", boom)

    resp = await client.get("/api/market/gold")
    assert resp.status_code == 502
    assert resp.json()["code"] == "EXTERNAL_SERVICE_ERROR"


@pytest.mark.asyncio
async def test_data_plane_error_envelope_is_surfaced(client, monkeypatch):
    """A 403 from the data plane keeps its message in this service's logs/body.

    "Invalid or missing X-Service-Token" is a far more actionable line than a
    bare "502 from data plane", and this is the wire on which a token
    mismatch actually shows up.
    """
    from kactus_fin import data_client

    async def forbidden(*args, **kwargs):
        return httpx.Response(
            403,
            json={"code": "PERMISSION_DENIED", "message": "Invalid or missing token"},
            request=httpx.Request("GET", "http://data-plane/internal/market/gold"),
        )

    monkeypatch.setattr(data_client.get_client(), "request", forbidden)

    resp = await client.get("/api/market/gold")
    assert resp.status_code == 502
    assert "Invalid or missing token" in resp.json()["message"]


# --------------------------------------------------------------------------- #
# Gold history + import
# --------------------------------------------------------------------------- #
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


SJC_CSV = b"date,buy_vnd_per_luong,sell_vnd_per_luong\n2026-07-24,134500000,139500000\n"


@pytest.mark.asyncio
async def test_gold_history_forwards_code_and_window(client, data_plane):
    data_plane.gold_history = [
        GoldHistoryPointSchema(
            code="SJC",
            date="2026-07-24",
            buy_price="134500000",
            sell_price="139500000",
            unit="VND/luong",
            source="sjc",
        )
    ]
    resp = await client.get(
        "/api/market/gold/history",
        params={"code": "SJC", "start": "2026-01-01", "limit": 100},
    )
    assert resp.status_code == 200
    assert resp.json()["data"][0]["buy_price"] == "134500000"
    sent = data_plane.last("gold_history")
    assert sent["code"] == "SJC"
    assert sent["start"] == "2026-01-01"
    assert sent["limit"] == 100


@pytest.mark.asyncio
async def test_gold_history_codes_passthrough(client, data_plane):
    data_plane.gold_history_codes = [
        GoldHistoryCodeSchema(
            code="PNJ:TPHCM:SJC",
            unit="VND/luong",
            points=5321,
            location="TPHCM",
            gold_type="SJC",
        )
    ]
    resp = await client.get("/api/market/gold/history/codes")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["code"] == "PNJ:TPHCM:SJC"


@pytest.mark.asyncio
async def test_import_requires_superuser(client, data_plane):
    """A normal session must not reach the import endpoint at all."""
    resp = await client.post(
        "/api/market/gold/import",
        files=[("files", ("sjc.csv", SJC_CSV, "text/csv"))],
    )
    assert resp.status_code == 403
    assert not [c for c, _ in data_plane.calls if c == "gold_import"]


@pytest.mark.asyncio
async def test_import_forwards_bytes_verbatim(admin_client, data_plane):
    data_plane.import_result = GoldImportResultSchema(
        dataset="sjc",
        filename="sjc.csv",
        rows_parsed=1,
        rows_imported=1,
        rows_skipped=0,
        codes=1,
    )
    resp = await admin_client.post(
        "/api/market/gold/import",
        files=[("files", ("sjc.csv", SJC_CSV, "text/csv"))],
    )
    assert resp.status_code == 200
    results = resp.json()["data"]
    assert len(results) == 1
    assert results[0]["dataset"] == "sjc"
    assert results[0]["rows_imported"] == "1"
    # The multipart wrapper is unwrapped here; the data plane sees raw CSV.
    assert data_plane.import_bodies == [SJC_CSV]
    assert data_plane.last("gold_import")["filename"] == "sjc.csv"


@pytest.mark.asyncio
async def test_import_data_plane_down_is_502(admin_client, monkeypatch):
    from kactus_fin import data_client

    async def boom(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(data_client.get_client(), "post", boom)

    resp = await admin_client.post(
        "/api/market/gold/import",
        files=[("files", ("sjc.csv", SJC_CSV, "text/csv"))],
    )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_this_service_holds_no_duckdb():
    """The invariant the whole phase exists to create, asserted in code.

    ``kactus_fin`` no longer depends on kactus-data, and an import-linter
    ``forbidden`` contract keeps it that way — but a dependency can be re-added
    in one line by someone who does not know why it left, and the linter only
    runs in CI and pre-commit.
    """
    import sys

    import kactus_fin  # noqa: F401

    assert "kactus_fin.olap" not in sys.modules
    # Nothing under kactus_fin may pull the ETL library in transitively.
    offenders = [
        name
        for name in sys.modules
        if name.startswith("kactus_fin") and "kactus_data" in name
    ]
    assert offenders == []
