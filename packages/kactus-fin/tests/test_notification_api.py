"""Tests for the kactus-fin notification API.

In-memory SQLite (OLTP). ASGITransport does not run lifespan, so no portfolio
runtime is needed. ``Notifier`` is monkeypatched in the test/send cases so we
exercise routing + ownership + secret-masking without hitting Telegram/Slack.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.notification import dispatcher
from kactus_common.notification.const import NotificationChannelType
from kactus_common.notification.service import NotificationChannelService
from kactus_common.user import auth as auth_mod
from kactus_common.user.model import User

TEST_DB_URL = "sqlite+aiosqlite://"
TEST_KEY = Fernet.generate_key().decode()

TELEGRAM_BODY = {
    "name": "My Bot",
    "channel_type": "telegram",
    "config": {"bot_token": "secret-token", "chat_id": "123456", "parse_mode": "HTML"},
}


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


# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_requires_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/notifications")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_crud_and_secret_masking(client):
    # Create
    resp = await client.post("/api/notifications", json=TELEGRAM_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0"
    data = body["data"]
    cid = data["id"]
    # Secret masked, non-secret kept.
    assert data["config"]["bot_token"] == "***"
    assert data["config"]["chat_id"] == "123456"

    # List
    resp = await client.get("/api/notifications")
    assert resp.json()["data"]["total"] == 1

    # Get one — still masked
    resp = await client.get(f"/api/notifications/{cid}")
    assert resp.json()["data"]["config"]["bot_token"] == "***"

    # Update
    resp = await client.put(
        f"/api/notifications/{cid}", json={"name": "Renamed", "is_active": False}
    )
    assert resp.json()["data"]["name"] == "Renamed"
    assert resp.json()["data"]["is_active"] is False

    # Delete
    assert (await client.delete(f"/api/notifications/{cid}")).status_code == 200
    assert (await client.get("/api/notifications")).json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_create_invalid_config_is_400(client):
    resp = await client.post(
        "/api/notifications",
        json={"name": "bad", "channel_type": "telegram", "config": {}},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_ownership_returns_404(client, db, seed_user):
    # A channel owned by someone else must be invisible (404, not 403).
    async with db.get_session() as session:
        other = await NotificationChannelService.create(
            session,
            owner_id=seed_user.id + 999,
            name="theirs",
            channel_type=NotificationChannelType.TELEGRAM,
            config={"bot_token": "x", "chat_id": "1"},
        )
        other_id = other.id
    resp = await client.get(f"/api/notifications/{other_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_test_endpoint(client, monkeypatch):
    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]

    async def _ok(channel):
        return True

    monkeypatch.setattr(dispatcher.Notifier, "test", staticmethod(_ok))
    resp = await client.post(f"/api/notifications/{cid}/test")
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "ok"


@pytest.mark.asyncio
async def test_test_endpoint_failure_is_502(client, monkeypatch):
    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]

    async def _fail(channel):
        return False

    monkeypatch.setattr(dispatcher.Notifier, "test", staticmethod(_fail))
    resp = await client.post(f"/api/notifications/{cid}/test")
    assert resp.status_code == 502
    assert resp.json()["code"] == "EXTERNAL_SERVICE_ERROR"


@pytest.mark.asyncio
async def test_send_endpoint(client, monkeypatch):
    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]

    captured = {}

    async def _send(channel, event):
        captured["title"] = event.title
        captured["channel_id"] = channel.id

    monkeypatch.setattr(dispatcher.Notifier, "send_event", staticmethod(_send))
    resp = await client.post(
        f"/api/notifications/{cid}/send",
        json={"title": "Giá vàng", "body": "SJC tăng", "level": "warning"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "sent"
    assert captured["title"] == "Giá vàng"
    assert str(captured["channel_id"]) == str(cid)
