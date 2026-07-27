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
from kactus_common.project.service import ProjectService
from kactus_common.user import auth as auth_mod
from kactus_common.user.context import set_current_project_id
from kactus_common.user.model import User
from kactus_notification.model import NotificationChannel
from kactus_notification.schema import ZaloPAChannelConfig, ZaloRecipientTarget

TEST_DB_URL = "sqlite+aiosqlite://"
TEST_KEY = Fernet.generate_key().decode()

_CONFIG = ZaloPAChannelConfig(
    cookies={"zpdid": "d"},
    imei="d",
    zpw_sek="z",
    zpsid="p",
    secret_key="k",
    user_agent="ua",
    recipients=[
        ZaloRecipientTarget(thread_id="42", thread_type=0, name="Bob"),
        ZaloRecipientTarget(thread_id="g1", thread_type=1, name="Team"),
    ],
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
        # A non-admin user gets a personal project on creation; the API is now
        # project-scoped, so tests need one selected. Stash its id for the cookie.
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
        # Select the personal project (backend reads the kactus_project_id cookie).
        c.cookies.set("kactus_project_id", str(seed_user._project_id))
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


async def _create_channel(client, monkeypatch, name="Gold alerts") -> dict:
    """POST the create endpoint with the config-assembly seam faked."""
    from kactus_fin.notification import zalo_pa_api

    captured: dict = {}

    async def _build(session_id, *, recipients):
        captured["recipients"] = recipients
        return _CONFIG

    monkeypatch.setattr(zalo_pa_api, "build_channel_config", _build)
    resp = await client.post(
        "/api/notifications/zalo-pa/channels",
        json={
            "session_id": "s1",
            "name": name,
            "recipients": [
                {"id": "42", "name": "Bob", "is_group": False},
                {"id": "g1", "name": "Team", "avatar": "t.png", "is_group": True},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    data["_captured_targets"] = captured["recipients"]
    return data


@pytest.mark.asyncio
async def test_create_channel_assembles_config_server_side(client, monkeypatch):
    data = await _create_channel(client, monkeypatch)
    assert data["channel_type"] == "zalo_pa"
    assert data["name"] == "Gold alerts"
    # The picker input is mapped to stored targets (is_group → thread_type).
    targets = data["_captured_targets"]
    assert [(t.thread_id, t.thread_type) for t in targets] == [("42", 0), ("g1", 1)]
    # Session secrets masked on the way out; conversation display kept.
    assert data["config"]["secret_key"] == "***"
    assert data["config"]["cookies"] == "***"
    assert [r["thread_id"] for r in data["config"]["recipients"]] == ["42", "g1"]
    assert data["config"]["account_name"] == "Me"

    # It shows up in the generic channel list (shared model).
    listed = await client.get("/api/notifications")
    assert listed.json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_create_channel_requires_recipients(client):
    resp = await client.post(
        "/api/notifications/zalo-pa/channels",
        json={"session_id": "s1", "name": "Empty", "recipients": []},
    )
    assert resp.status_code == 422  # min_length=1 on the request schema


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


# --------------------------------------------------------------------------- #
# Channel-level conversations (edit picker) + ⚡ test-message
# --------------------------------------------------------------------------- #
async def _stored_config(db, seed_user, channel_id: int) -> dict:
    """Read the decrypted config straight from the DB (bypasses API masking)."""
    set_current_project_id(seed_user._project_id)
    try:
        async with db.get_session() as session:
            channel = await NotificationChannel.first_or_404(session, id=channel_id)
            return dict(channel.config)
    finally:
        set_current_project_id(None)


@pytest.mark.asyncio
async def test_channel_recipients_lists_from_stored_session(client, monkeypatch):
    from kactus_fin.notification import zalo_pa_api
    from kactus_notification.schema import Recipient

    created = await _create_channel(client, monkeypatch)

    async def _live(config, query=""):
        assert config.imei == "d"  # hydrated from the stored (decrypted) config
        return [Recipient(id="u9", name="Alice", avatar="a.png", is_group=False)]

    monkeypatch.setattr(zalo_pa_api, "list_channel_recipients", _live)
    resp = await client.get(
        f"/api/notifications/zalo-pa/channels/{created['id']}/recipients"
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1 and data["items"][0]["id"] == "u9"


@pytest.mark.asyncio
async def test_channel_recipients_rejects_non_zalo_channel(client):
    resp = await client.post(
        "/api/notifications",
        json={
            "name": "TG",
            "channel_type": "telegram",
            "config": {"bot_token": "T", "chat_id": "1"},
        },
    )
    channel_id = resp.json()["data"]["id"]
    listed = await client.get(
        f"/api/notifications/zalo-pa/channels/{channel_id}/recipients"
    )
    assert listed.status_code == 400


@pytest.mark.asyncio
async def test_update_recipients_replaces_targets_and_keeps_secrets(
    client, db, seed_user, monkeypatch
):
    created = await _create_channel(client, monkeypatch)
    resp = await client.put(
        f"/api/notifications/zalo-pa/channels/{created['id']}/recipients",
        json={"recipients": [{"id": "g9", "name": "Crew", "is_group": True}]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert [
        (r["thread_id"], r["thread_type"]) for r in data["config"]["recipients"]
    ] == [("g9", 1)]
    # Credentials survive untouched (never round-tripped through the client).
    stored = await _stored_config(db, seed_user, created["id"])
    assert stored["secret_key"] == "k"
    assert stored["cookies"] == {"zpdid": "d"}
    assert [r["thread_id"] for r in stored["recipients"]] == ["g9"]


@pytest.mark.asyncio
async def test_test_message_sends_greeting_to_all(client, monkeypatch):
    from kactus_fin.notification import zalo_pa_api

    created = await _create_channel(client, monkeypatch)
    sent_with: dict = {}

    async def _greet(config, text):
        sent_with["text"] = text
        return [
            {"thread_id": "42", "name": "Bob", "ok": True, "error": None},
            {"thread_id": "g1", "name": "Team", "ok": False, "error": "kicked"},
        ]

    monkeypatch.setattr(zalo_pa_api, "send_greeting_to_recipients", _greet)
    resp = await client.post(
        f"/api/notifications/zalo-pa/channels/{created['id']}/test-message"
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert sent_with["text"] == "Hello, nice to meet you"
    assert data["sent"] == 1 and data["failed"] == 1
    assert data["results"][1]["error"] == "kicked"


@pytest.mark.asyncio
async def test_test_message_blocked_on_inactive_channel(client, monkeypatch):
    created = await _create_channel(client, monkeypatch)
    deactivated = await client.put(
        f"/api/notifications/{created['id']}", json={"is_active": False}
    )
    assert deactivated.status_code == 200
    resp = await client.post(
        f"/api/notifications/zalo-pa/channels/{created['id']}/test-message"
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_reauth_swaps_credentials_keeps_recipients(
    client, db, seed_user, monkeypatch
):
    from kactus_fin.notification import zalo_pa_api

    created = await _create_channel(client, monkeypatch)

    async def _creds(session_id):
        return {
            "cookies": {"zpdid": "d2"},
            "imei": "d2",
            "zpw_sek": "z2",
            "zpsid": "p2",
            "secret_key": "k2",
            "user_agent": "ua2",
        }

    monkeypatch.setattr(zalo_pa_api, "session_credentials", _creds)
    resp = await client.put(
        f"/api/notifications/zalo-pa/channels/{created['id']}/reauth",
        json={"session_id": "s2"},
    )
    assert resp.status_code == 200
    stored = await _stored_config(db, seed_user, created["id"])
    assert stored["imei"] == "d2" and stored["secret_key"] == "k2"
    assert [r["thread_id"] for r in stored["recipients"]] == ["42", "g1"]
