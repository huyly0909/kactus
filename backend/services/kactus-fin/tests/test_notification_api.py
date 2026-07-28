"""Tests for the kactus-fin notification API.

In-memory SQLite (OLTP). ASGITransport does not run lifespan, so no portfolio
runtime is needed. ``Notifier`` is monkeypatched in the test/send cases so we
exercise routing + ownership + secret-masking without hitting Telegram/Slack.
"""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from kactus_common.database.oltp import session as session_mod
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.project.service import ProjectService
from kactus_common.redis import client as redis_client_mod
from kactus_common.user import auth as auth_mod
from kactus_common.user.context import set_current_project_id
from kactus_common.user.model import User
from kactus_fin.notification.consumer import deliver
from kactus_notification import dispatcher
from kactus_notification import queue as queue_mod
from kactus_notification.const import NotificationChannelType
from kactus_notification.queue import (
    CONSUMER_GROUP,
    NotificationQueueConsumer,
    stream_key,
)
from kactus_notification.service import NotificationChannelService

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
async def redis_queue(app, monkeypatch):
    """Turn the queue on for one test: fake Redis + the ``redis`` backend.

    Both halves are needed — ``_queue_enabled()`` gates on
    ``coordination_backend`` precisely so a deployment without Redis keeps
    working, so flipping only the client would still send inline.
    """
    from kactus_common.config import settings

    server = fakeredis.aioredis.FakeRedis()
    for module in (redis_client_mod, queue_mod):
        monkeypatch.setattr(module, "get_redis", lambda: server, raising=False)
    monkeypatch.setattr(settings, "coordination_backend", "redis", raising=False)
    yield server
    await server.flushall()
    await server.aclose()


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

    async def _ok(channel, session=None):
        return True

    monkeypatch.setattr(dispatcher.Notifier, "test", staticmethod(_ok))
    resp = await client.post(f"/api/notifications/{cid}/test")
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "ok"


@pytest.mark.asyncio
async def test_test_endpoint_records_history(client, monkeypatch):
    """The real Notifier.test writes a trigger=test row so a dead probe is visible."""
    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]

    class _Impl:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def test_connection(self):
            return False

    monkeypatch.setattr(dispatcher, "build_channel", lambda t, c: _Impl())
    resp = await client.post(f"/api/notifications/{cid}/test")
    assert resp.status_code == 502

    logs = (await client.get(f"/api/notifications/{cid}/logs")).json()["data"]
    assert logs["total"] == 1
    assert logs["items"][0]["trigger"] == "test"
    assert logs["items"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_test_endpoint_failure_is_502(client, monkeypatch):
    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]

    async def _fail(channel, session=None):
        return False

    monkeypatch.setattr(dispatcher.Notifier, "test", staticmethod(_fail))
    resp = await client.post(f"/api/notifications/{cid}/test")
    assert resp.status_code == 502
    assert resp.json()["code"] == "EXTERNAL_SERVICE_ERROR"


@pytest.mark.asyncio
async def test_send_endpoint_inline_on_the_memory_backend(client, monkeypatch):
    """No Redis ⇒ no queue: the endpoint sends inline, as it always did.

    Still 202 — the status describes the contract ("we have taken this"), not
    which coordination backend happens to be configured, so the frontend does
    not have to care which deployment it is talking to.
    """
    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]

    captured = {}

    async def _send(session, channel, event, **kwargs):
        captured["title"] = event.title
        captured["channel_id"] = channel.id

    monkeypatch.setattr(dispatcher.Notifier, "send_event", staticmethod(_send))
    resp = await client.post(
        f"/api/notifications/{cid}/send",
        json={"title": "Giá vàng", "body": "SJC tăng", "level": "warning"},
    )
    assert resp.status_code == 202
    assert resp.json()["data"]["message"] == "sent"
    assert captured["title"] == "Giá vàng"
    assert str(captured["channel_id"]) == str(cid)


@pytest.mark.asyncio
async def test_send_blocked_on_inactive_channel(client):
    """Deactivate must mean silence — /send fast-fails with 409 before enqueue."""
    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]
    await client.put(f"/api/notifications/{cid}", json={"is_active": False})
    resp = await client.post(f"/api/notifications/{cid}/send", json={"title": "nope"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_masked_config_update_keeps_stored_secrets(client, db, seed_user):
    """PUT-ing back a fetched (masked) config must not clobber real secrets."""
    created = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()[
        "data"
    ]
    cid = created["id"]
    masked = created["config"]  # bot_token is "***" here
    assert masked["bot_token"] == "***"
    masked["chat_id"] = "999"  # a legitimate non-secret edit
    resp = await client.put(f"/api/notifications/{cid}", json={"config": masked})
    assert resp.status_code == 200
    assert resp.json()["data"]["config"]["chat_id"] == "999"

    set_current_project_id(seed_user._project_id)
    try:
        async with db.get_session() as session:
            channel = await NotificationChannelService.get_or_404(session, int(cid))
            assert channel.config["bot_token"] == "secret-token"  # survived the mask
            assert channel.config["chat_id"] == "999"
    finally:
        set_current_project_id(None)


@pytest.mark.asyncio
async def test_send_queues_instead_of_blocking_on_a_lagging_channel(
    client, redis_queue, monkeypatch
):
    """The reason Phase 3 exists.

    ``Notifier.send_event`` retries inline with exponential backoff, so a
    channel that hangs used to hold the request for as long as that took. The
    stand-in here sleeps far longer than any acceptable response; the assertion
    is that the request never waits for it and the work is on the stream
    instead.
    """
    import time

    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]

    async def _hangs(session, channel, event, **kwargs):
        await asyncio.sleep(30)

    monkeypatch.setattr(dispatcher.Notifier, "send_event", staticmethod(_hangs))

    started = time.perf_counter()
    resp = await client.post(
        f"/api/notifications/{cid}/send",
        json={"title": "Giá vàng", "body": "SJC tăng", "level": "warning"},
    )
    elapsed = time.perf_counter() - started

    assert resp.status_code == 202
    assert resp.json()["data"]["message"] == "queued"
    assert elapsed < 0.1  # the plan's bar; the send itself would take 30s
    assert await redis_queue.xlen(stream_key()) == 1


@pytest.mark.asyncio
async def test_queued_send_is_delivered_by_the_consumer(
    client, redis_queue, seed_user, monkeypatch
):
    """End of the rope: what the endpoint enqueued is what the consumer sends."""
    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]

    captured = {}

    async def _send(session, channel, event, **kwargs):
        captured["title"] = event.title
        captured["channel_id"] = channel.id
        captured["trigger"] = kwargs.get("trigger")

    monkeypatch.setattr(dispatcher.Notifier, "send_event", staticmethod(_send))
    await client.post(
        f"/api/notifications/{cid}/send",
        json={"title": "Giá vàng", "body": "SJC tăng", "level": "warning"},
    )

    consumer = NotificationQueueConsumer(
        deliver, consumer_name="test", block_ms=0, claim_idle_ms=0
    )
    assert await consumer.run_once() == 1
    assert captured["title"] == "Giá vàng"
    assert str(captured["channel_id"]) == str(cid)


@pytest.mark.asyncio
async def test_consumer_drops_an_entry_whose_channel_was_deleted(
    client, redis_queue, monkeypatch
):
    """A queued send outlives its channel — the delete happens meanwhile.

    Redelivering cannot make the channel exist again, so the entry is acked
    rather than left to be reclaimed forever.
    """
    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]
    await client.post(
        f"/api/notifications/{cid}/send",
        json={"title": "Giá vàng", "body": "SJC tăng", "level": "info"},
    )
    await client.delete(f"/api/notifications/{cid}")

    sent = False

    async def _send(session, channel, event, **kwargs):
        nonlocal sent
        sent = True

    monkeypatch.setattr(dispatcher.Notifier, "send_event", staticmethod(_send))
    consumer = NotificationQueueConsumer(
        deliver, consumer_name="test", block_ms=0, claim_idle_ms=0
    )
    assert await consumer.run_once() == 1  # acked...
    assert sent is False  # ...without sending


@pytest.mark.asyncio
async def test_consumer_acks_a_permanently_failing_send(
    client, redis_queue, monkeypatch
):
    """A failed send is *handled*, not unhandled.

    ``send_event`` already exhausted its bounded retry and wrote a FAILED
    ``NotificationLog``. Leaving the entry pending would re-run that whole retry
    loop for as long as the channel stays broken — a busy loop against a third
    party, with a duplicate audit row each time round.
    """
    from kactus_common.exceptions import ExternalServiceError

    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]
    await client.post(
        f"/api/notifications/{cid}/send",
        json={"title": "Giá vàng", "body": "SJC tăng", "level": "info"},
    )

    async def _fails(session, channel, event, **kwargs):
        raise ExternalServiceError("telegram: 401 unauthorized")

    monkeypatch.setattr(dispatcher.Notifier, "send_event", staticmethod(_fails))
    consumer = NotificationQueueConsumer(
        deliver, consumer_name="test", block_ms=0, claim_idle_ms=0
    )
    assert await consumer.run_once() == 1
    assert (
        await redis_queue.xpending_range(
            stream_key(), CONSUMER_GROUP, min="-", max="+", count=10
        )
        == []
    )


@pytest.mark.asyncio
async def test_test_endpoint_stays_synchronous(client, redis_queue, monkeypatch):
    """``/test`` must not be queued even with the queue on.

    The user is sitting in front of a credentials form waiting to hear whether
    they work; a 202 there answers nothing.
    """

    async def _test(channel, session=None):
        return True

    monkeypatch.setattr(dispatcher.Notifier, "test", staticmethod(_test))
    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]

    resp = await client.post(f"/api/notifications/{cid}/test")
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "ok"
    assert await redis_queue.xlen(stream_key()) == 0


@pytest.mark.asyncio
async def test_logs_endpoint(client, db, seed_user):
    from kactus_notification.const import NotificationLogStatus, NotificationTrigger
    from kactus_notification.schema import NotificationEvent
    from kactus_notification.service import NotificationLogService

    cid = (await client.post("/api/notifications", json=TELEGRAM_BODY)).json()["data"][
        "id"
    ]

    # Seed two audit rows directly (mirrors what Notifier.send_event writes).
    async with db.get_session() as session:
        channel = await NotificationChannelService.get_or_404(
            session, channel_id=int(cid)
        )
        await NotificationLogService.record(
            session,
            channel=channel,
            event=NotificationEvent(title="ok"),
            status=NotificationLogStatus.SUCCESS,
            attempts=1,
            error=None,
            trigger=NotificationTrigger.MANUAL,
        )
        await NotificationLogService.record(
            session,
            channel=channel,
            event=NotificationEvent(title="boom"),
            status=NotificationLogStatus.FAILED,
            attempts=3,
            error="down",
            trigger=NotificationTrigger.MANUAL,
        )

    resp = await client.get(f"/api/notifications/{cid}/logs")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    titles = {item["event_title"] for item in data["items"]}
    assert titles == {"ok", "boom"}
    failed = next(i for i in data["items"] if i["status"] == "failed")
    assert failed["attempts"] == 3
    assert failed["error"] == "down"


@pytest.mark.asyncio
async def test_logs_endpoint_ownership_404(client, db, seed_user):
    async with db.get_session() as session:
        other = await NotificationChannelService.create(
            session,
            owner_id=seed_user.id + 999,
            name="theirs",
            channel_type=NotificationChannelType.TELEGRAM,
            config={"bot_token": "x", "chat_id": "1"},
        )
        other_id = other.id
    resp = await client.get(f"/api/notifications/{other_id}/logs")
    assert resp.status_code == 404
