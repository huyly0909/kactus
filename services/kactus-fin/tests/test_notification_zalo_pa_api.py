"""Tests for the Zalo PA onboarding API (kactus-fin).

The zlapi/curl_cffi transport is faked at the ``zalo_pa_api`` seam — we exercise
routing + auth + the server-side config assembly + secret masking, not Zalo.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.user import auth as auth_mod
from kactus_common.user.model import User
from kactus_notification.schema import ZaloPAChannelConfig

TEST_DB_URL = "sqlite+aiosqlite://"
TEST_KEY = Fernet.generate_key().decode()

_CONFIG = ZaloPAChannelConfig(
    cookies={"zpdid": "d"},
    imei="d",
    zpw_sek="z",
    zpsid="p",
    secret_key="k",
    user_agent="ua",
    thread_id="42",
    thread_type=0,
    recipient_name="Bob",
    zalo_user_id="u1",
    account_name="Me",
)


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

    register_settings(
        Settings(
            enable_portfolio_scheduler=False,
            db_path=str(tmp_path / "t.duckdb"),
            encryption_key=TEST_KEY,
        )
    )
    session_mod._db = db
    auth_mod._auth = None
    _app = create_app()
    yield _app
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


@pytest.mark.asyncio
async def test_qr_and_recipients_require_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post("/api/notifications/zalo-pa/qr/generate")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_qr_generate(client, monkeypatch):
    from kactus_fin.notification import zalo_pa_api

    async def _gen(session_id):
        return {"code": "CODE", "image_url": "IMG"}

    monkeypatch.setattr(zalo_pa_api, "generate_qr", _gen)
    resp = await client.post("/api/notifications/zalo-pa/qr/generate")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["code"] == "CODE" and data["image_url"] == "IMG"
    assert data["session_id"]  # server-minted handle


@pytest.mark.asyncio
async def test_create_channel_assembles_config_server_side(client, monkeypatch):
    from kactus_fin.notification import zalo_pa_api

    async def _build(*a, **k):
        return _CONFIG

    monkeypatch.setattr(zalo_pa_api, "build_channel_config", _build)
    resp = await client.post(
        "/api/notifications/zalo-pa/channels",
        json={
            "session_id": "s1",
            "name": "Gold alerts",
            "thread_id": "42",
            "thread_type": 0,
            "recipient_name": "Bob",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["channel_type"] == "zalo_pa"
    assert data["name"] == "Gold alerts"
    # Session secrets masked on the way out; recipient display kept.
    assert data["config"]["secret_key"] == "***"
    assert data["config"]["thread_id"] == "42"
    assert data["config"]["account_name"] == "Me"

    # It shows up in the generic channel list (shared model).
    listed = await client.get("/api/notifications")
    assert listed.json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_recipients_endpoint(client, monkeypatch):
    from kactus_fin.notification import zalo_pa_api
    from kactus_notification.schema import Recipient

    async def _recipients(session_id, query):
        return [
            Recipient(id="u9", name="Alice", is_group=False),
            Recipient(id="g1", name="Team", is_group=True),
        ]

    monkeypatch.setattr(zalo_pa_api, "list_session_recipients", _recipients)
    resp = await client.get("/api/notifications/zalo-pa/sessions/s1/recipients")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert {r["id"] for r in data["items"]} == {"u9", "g1"}
