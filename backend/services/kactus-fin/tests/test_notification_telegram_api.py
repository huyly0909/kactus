"""Tests for the Telegram onboarding API (kactus-fin).

The Bot API is faked at the ``telegram_api`` seam — this exercises routing,
auth, the type guard, and the server-side chat_id merge, not Telegram.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.project.service import ProjectService
from kactus_common.user import auth as auth_mod
from kactus_common.user.context import set_current_project_id
from kactus_common.user.model import User
from kactus_notification.channels.telegram.schema import TelegramBotInfo, TelegramChat

TEST_DB_URL = "sqlite+aiosqlite://"
TEST_KEY = Fernet.generate_key().decode()

BOT_TOKEN = "123456:AAF-secret"
CHANNEL_CHAT = TelegramChat(id="-1001234567890", title="Gold Alerts", type="channel")
GROUP_CHAT = TelegramChat(id="-42", title="Trading Desk", type="group")


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
        project = await ProjectService.ensure_personal_project(session, user=user)
        user._project_id = project.id
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
        c.cookies.set("kactus_project_id", str(seed_user._project_id))
        yield c


async def _create_telegram_channel(client, name="Gold alerts") -> dict:
    resp = await client.post(
        "/api/notifications",
        json={
            "name": name,
            "channel_type": "telegram",
            "config": {"bot_token": BOT_TOKEN, "chat_id": CHANNEL_CHAT.id},
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# --------------------------------------------------------------------------- #
# Pre-channel routes
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_setup_routes_require_auth(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/api/notifications/telegram/verify", json={"bot_token": BOT_TOKEN}
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_returns_bot_identity(client, monkeypatch):
    from kactus_fin.notification import telegram_api

    async def _verify(bot_token, timeout=10.0):
        assert bot_token == BOT_TOKEN
        return TelegramBotInfo(id="9", username="gold_bot", first_name="Gold")

    monkeypatch.setattr(telegram_api, "verify_bot", _verify)
    resp = await client.post(
        "/api/notifications/telegram/verify", json={"bot_token": BOT_TOKEN}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "gold_bot"


@pytest.mark.asyncio
async def test_chats_discovery_returns_a_pagination(client, monkeypatch):
    from kactus_fin.notification import telegram_api

    async def _discover(bot_token, timeout=10.0):
        return [CHANNEL_CHAT, GROUP_CHAT]

    monkeypatch.setattr(telegram_api, "discover_chats", _discover)
    resp = await client.post(
        "/api/notifications/telegram/chats", json={"bot_token": BOT_TOKEN}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert [c["id"] for c in data["items"]] == ["-1001234567890", "-42"]


@pytest.mark.asyncio
async def test_empty_discovery_is_a_200_not_an_error(client, monkeypatch):
    """Nothing posted yet is the normal first run — the UI shows a guide."""
    from kactus_fin.notification import telegram_api

    async def _discover(bot_token, timeout=10.0):
        return []

    monkeypatch.setattr(telegram_api, "discover_chats", _discover)
    resp = await client.post(
        "/api/notifications/telegram/chats", json={"bot_token": BOT_TOKEN}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []


@pytest.mark.asyncio
async def test_resolve_chat_passes_the_username_through(client, monkeypatch):
    from kactus_fin.notification import telegram_api

    async def _resolve(bot_token, chat_id, timeout=10.0):
        assert chat_id == "@public_news"
        return TelegramChat(
            id="-1009", title="Public News", type="channel", username="public_news"
        )

    monkeypatch.setattr(telegram_api, "resolve_chat", _resolve)
    resp = await client.post(
        "/api/notifications/telegram/chats/resolve",
        json={"bot_token": BOT_TOKEN, "chat_id": "@public_news"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == "-1009"


# --------------------------------------------------------------------------- #
# Channel-scoped routes
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_channel_chats_uses_the_stored_token(client, monkeypatch):
    """Re-picking a chat must not require the client to resend the secret."""
    from kactus_fin.notification import telegram_api

    created = await _create_telegram_channel(client)
    seen: dict = {}

    async def _discover(bot_token, timeout=10.0):
        seen["bot_token"] = bot_token
        return [CHANNEL_CHAT, GROUP_CHAT]

    monkeypatch.setattr(telegram_api, "discover_chats", _discover)
    resp = await client.get(
        f"/api/notifications/telegram/channels/{created['id']}/chats"
    )

    assert resp.status_code == 200
    assert seen["bot_token"] == BOT_TOKEN  # decrypted from the row, not the request
    assert resp.json()["data"]["total"] == 2


@pytest.mark.asyncio
async def test_update_chat_keeps_the_bot_token(client, db):
    """The merge is server-side — a masked config must never clobber the token."""
    created = await _create_telegram_channel(client)
    assert created["config"]["bot_token"] == "***"  # what a client would echo back

    resp = await client.put(
        f"/api/notifications/telegram/channels/{created['id']}/chat",
        json={"chat_id": GROUP_CHAT.id},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["config"]["chat_id"] == GROUP_CHAT.id

    from kactus_notification.model import NotificationChannel

    async with db.get_session() as session:
        set_current_project_id(None)
        row = await session.get(NotificationChannel, int(created["id"]))
        assert row.config["bot_token"] == BOT_TOKEN  # still the real secret
        assert row.config["chat_id"] == GROUP_CHAT.id


@pytest.mark.asyncio
async def test_test_message_sends_for_real_and_is_logged(client, monkeypatch):
    """⚡ must actually post — that is what /test (getMe) cannot prove."""
    from kactus_notification import dispatcher

    created = await _create_telegram_channel(client)
    sent: list = []

    class _Impl:
        retryable_exceptions = ()
        last_targets: list = []

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def send(self, rendered):
            sent.append(rendered.text)

    monkeypatch.setattr(dispatcher, "build_channel", lambda t, c: _Impl())
    resp = await client.post(
        f"/api/notifications/telegram/channels/{created['id']}/test-message"
    )
    assert resp.status_code == 200
    assert len(sent) == 1 and "Hello" in sent[0]

    logs = await client.get(f"/api/notifications/{created['id']}/logs")
    rows = logs.json()["data"]["items"]
    assert rows[0]["trigger"] == "test"
    assert rows[0]["status"] == "success"


@pytest.mark.asyncio
async def test_test_message_blocked_on_an_inactive_channel(client):
    """Deactivate must mean silence — the greeting is a real message."""
    created = await _create_telegram_channel(client)
    await client.put(f"/api/notifications/{created['id']}", json={"is_active": False})

    resp = await client.post(
        f"/api/notifications/telegram/channels/{created['id']}/test-message"
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_reauth_swaps_the_token_and_keeps_the_chat(client, db, monkeypatch):
    from kactus_fin.notification import telegram_api

    created = await _create_telegram_channel(client)

    async def _verify(bot_token, timeout=10.0):
        return TelegramBotInfo(id="9", username="gold_bot", first_name="Gold")

    monkeypatch.setattr(telegram_api, "verify_bot", _verify)
    resp = await client.put(
        f"/api/notifications/telegram/channels/{created['id']}/reauth",
        json={"bot_token": "999:NEW-token"},
    )
    assert resp.status_code == 200

    from kactus_notification.model import NotificationChannel

    async with db.get_session() as session:
        set_current_project_id(None)
        row = await session.get(NotificationChannel, int(created["id"]))
        assert row.config["bot_token"] == "999:NEW-token"
        assert row.config["chat_id"] == CHANNEL_CHAT.id  # target preserved


@pytest.mark.asyncio
async def test_reauth_refuses_a_token_that_fails_getme(client, db, monkeypatch):
    """A typo must not replace a working credential with a dead one."""
    from kactus_common.exceptions import ExternalServiceError
    from kactus_fin.notification import telegram_api

    created = await _create_telegram_channel(client)

    async def _verify(bot_token, timeout=10.0):
        raise ExternalServiceError("Telegram getMe failed: Unauthorized")

    monkeypatch.setattr(telegram_api, "verify_bot", _verify)
    resp = await client.put(
        f"/api/notifications/telegram/channels/{created['id']}/reauth",
        json={"bot_token": "bad"},
    )
    assert resp.status_code >= 400

    from kactus_notification.model import NotificationChannel

    async with db.get_session() as session:
        set_current_project_id(None)
        row = await session.get(NotificationChannel, int(created["id"]))
        assert row.config["bot_token"] == BOT_TOKEN  # untouched


@pytest.mark.asyncio
async def test_channel_routes_reject_another_channel_type(client, monkeypatch):
    resp = await client.post(
        "/api/notifications",
        json={
            "name": "Slack ops",
            "channel_type": "slack",
            "config": {"webhook_url": "https://hooks.slack.com/services/x"},
        },
    )
    assert resp.status_code == 200
    slack_id = resp.json()["data"]["id"]

    resp = await client.put(
        f"/api/notifications/telegram/channels/{slack_id}/chat",
        json={"chat_id": "-1"},
    )
    assert resp.status_code == 400
