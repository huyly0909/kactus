"""Tests for the Notifier orchestrator.

Exercises the real send/test path — build_channel + template render + the
``asyncio.to_thread`` blocking helpers + connection lifecycle — with a fake
``requests`` session injected (no network), plus the synchronous bounded
retry/backoff and the :class:`NotificationLog` audit trail. Backoff delay is set
to 0 in the registered settings so retries don't sleep.
"""

from __future__ import annotations

import types

import pytest
import pytest_asyncio
import requests
from cryptography.fernet import Fernet
from kactus_common.config import CommonSettings, clear_settings, register_settings
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.exceptions import ExternalServiceError
from kactus_notification import dispatcher
from kactus_notification.channel import DeliveryTarget
from kactus_notification.channels.telegram import TelegramChannel, TelegramChannelConfig
from kactus_notification.config import NotificationSettings
from kactus_notification.const import NotificationLogStatus, NotificationTrigger
from kactus_notification.schema import NotificationEvent
from kactus_notification.service import NotificationLogService

TEST_DB_URL = "sqlite+aiosqlite://"
TEST_KEY = Fernet.generate_key().decode()


class _Settings(CommonSettings, NotificationSettings):
    """Composite settings, mirroring how kactus-fin merges the two branches.

    ``encryption_key`` comes from the kactus-common branch, the retry knobs from
    the kactus-notification one. A bare ``CommonSettings`` would silently drop
    the retry kwargs below (``extra="ignore"``) instead of rejecting them.
    """


@pytest_asyncio.fixture
async def db():
    register_settings(
        _Settings(
            encryption_key=TEST_KEY,
            notification_max_send_attempts=3,
            notification_retry_base_delay=0.0,  # no real sleeping in tests
        )
    )
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()
    clear_settings()


class FakeResponse:
    def __init__(self, status_code: int = 200, json_data: dict | None = None) -> None:
        self.status_code = status_code
        self._json = json_data or {}

    def json(self) -> dict:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class FakeSession:
    """A ``requests.Session`` stand-in that fails its first ``fail_times`` posts."""

    def __init__(
        self, response: FakeResponse | None = None, *, fail_times: int = 0
    ) -> None:
        self.response = response or FakeResponse()
        self.fail_times = fail_times
        self.calls = 0
        self.posts: list[dict] = []
        self.closed = False

    def post(self, url, json=None, timeout=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise requests.ConnectionError("boom")
        self.posts.append({"url": url, "json": json})
        return self.response

    def get(self, url, timeout=None):
        return self.response

    def close(self):
        self.closed = True


def _model(*, is_active: bool = True):
    """Minimal stand-in for the ORM channel — Notifier reads only these attrs."""
    return types.SimpleNamespace(
        id=1,
        owner_id=7,
        project_id=None,
        channel_type="telegram",
        config={"bot_token": "T", "chat_id": "1"},
        is_active=is_active,
    )


def _patch_channel(monkeypatch, fake: FakeSession) -> TelegramChannel:
    ch = TelegramChannel(TelegramChannelConfig(bot_token="T", chat_id="1"))
    # create_connection installs our fake instead of opening a real Session.
    monkeypatch.setattr(ch, "create_connection", lambda: setattr(ch, "_session", fake))
    monkeypatch.setattr(dispatcher, "build_channel", lambda t, c: ch)
    return ch


async def _logs(session):
    # The fake channel is unscoped (project_id=None), so logs land unscoped too.
    _total, logs = await NotificationLogService.list_for_project(session, None)
    return logs


@pytest.mark.asyncio
async def test_send_event_renders_and_delivers(db, monkeypatch):
    fake = FakeSession()
    _patch_channel(monkeypatch, fake)
    async with db.get_session() as session:
        await dispatcher.Notifier.send_event(
            session, _model(), NotificationEvent(title="Giá vàng", body="SJC tăng")
        )
        logs = await _logs(session)
    assert fake.posts and fake.posts[0]["url"].endswith("/botT/sendMessage")
    assert "Giá vàng" in fake.posts[0]["json"]["text"]
    assert fake.closed is True  # connection closed after send
    assert len(logs) == 1
    assert logs[0].status == NotificationLogStatus.SUCCESS
    assert logs[0].attempts == 1
    assert logs[0].event_title == "Giá vàng"


@pytest.mark.asyncio
async def test_send_event_retries_then_succeeds(db, monkeypatch):
    fake = FakeSession(fail_times=1)  # first attempt boom, second ok
    _patch_channel(monkeypatch, fake)
    async with db.get_session() as session:
        await dispatcher.Notifier.send_event(
            session, _model(), NotificationEvent(title="retry me")
        )
        logs = await _logs(session)
    assert fake.calls == 2
    assert len(logs) == 1
    assert logs[0].status == NotificationLogStatus.SUCCESS
    assert logs[0].attempts == 2


@pytest.mark.asyncio
async def test_send_event_exhausts_retries_and_logs_failure(db, monkeypatch):
    fake = FakeSession(fail_times=99)  # always boom
    _patch_channel(monkeypatch, fake)
    async with db.get_session() as session:
        with pytest.raises(ExternalServiceError):
            await dispatcher.Notifier.send_event(
                session, _model(), NotificationEvent(title="doomed")
            )
        logs = await _logs(session)
    assert fake.calls == 3  # notification_max_send_attempts
    assert len(logs) == 1
    assert logs[0].status == NotificationLogStatus.FAILED
    assert logs[0].attempts == 3
    assert logs[0].error


@pytest.mark.asyncio
async def test_send_event_deterministic_error_not_retried(db, monkeypatch):
    ch = _patch_channel(monkeypatch, FakeSession())

    def _boom(_message):
        raise ExternalServiceError("expired session")

    monkeypatch.setattr(ch, "send", _boom)
    async with db.get_session() as session:
        with pytest.raises(ExternalServiceError):
            await dispatcher.Notifier.send_event(
                session, _model(), NotificationEvent(title="nope")
            )
        logs = await _logs(session)
    assert len(logs) == 1
    assert logs[0].status == NotificationLogStatus.FAILED
    assert logs[0].attempts == 1  # deterministic → no retry


@pytest.mark.asyncio
async def test_send_event_skips_inactive_channel(db, monkeypatch):
    """is_active is enforced here — the single gate for inline + queued sends."""
    fake = FakeSession()
    _patch_channel(monkeypatch, fake)
    async with db.get_session() as session:
        await dispatcher.Notifier.send_event(
            session, _model(is_active=False), NotificationEvent(title="silence")
        )
        logs = await _logs(session)
    assert fake.posts == []  # nothing delivered
    assert logs == []  # and nothing logged — the channel is simply off


@pytest.mark.asyncio
async def test_send_event_records_each_failed_attempt(db, monkeypatch):
    """``attempts: 3`` alone cannot distinguish a flaky network from a dead token."""
    fake = FakeSession(fail_times=2)  # two booms, then delivered
    _patch_channel(monkeypatch, fake)
    async with db.get_session() as session:
        await dispatcher.Notifier.send_event(
            session, _model(), NotificationEvent(title="flaky", body="the content")
        )
        logs = await _logs(session)
    log = logs[0]
    assert log.status == NotificationLogStatus.SUCCESS
    assert log.attempts == 3
    assert [e["attempt"] for e in log.attempt_errors] == [1, 2]
    assert all("boom" in e["error"] for e in log.attempt_errors)
    assert all(e["at"] for e in log.attempt_errors)
    assert log.body == "the content"  # full content, not just the title


@pytest.mark.asyncio
async def test_send_event_records_per_conversation_outcome(db, monkeypatch):
    """A fan-out that only half worked must not read as a clean success."""
    ch = _patch_channel(monkeypatch, FakeSession())
    targets = [
        DeliveryTarget(thread_id="a", thread_type=0, name="Ann", ok=True),
        DeliveryTarget(thread_id="b", thread_type=1, name="Group", ok=True),
        DeliveryTarget(
            thread_id="c", thread_type=0, name="Cee", ok=False, error="blocked"
        ),
    ]

    def _fan_out(_message):
        ch.last_targets = targets

    monkeypatch.setattr(ch, "send", _fan_out)
    async with db.get_session() as session:
        await dispatcher.Notifier.send_event(
            session, _model(), NotificationEvent(title="partial")
        )
        logs = await _logs(session)
    log = logs[0]
    assert log.delivered_count == 2
    assert log.target_count == 3
    assert {t["name"] for t in log.targets} == {"Ann", "Group", "Cee"}
    failed = next(t for t in log.targets if not t["ok"])
    assert failed["error"] == "blocked"
    assert failed["thread_id"] == "c"


@pytest.mark.asyncio
async def test_send_event_records_targets_even_when_nothing_delivered(db, monkeypatch):
    """The all-failed case is exactly the one whose per-target errors we need."""
    ch = _patch_channel(monkeypatch, FakeSession())

    def _all_fail(_message):
        ch.last_targets = [
            DeliveryTarget(
                thread_id="a", thread_type=0, name="Ann", ok=False, error="expired"
            )
        ]
        raise ExternalServiceError("session dead")

    monkeypatch.setattr(ch, "send", _all_fail)
    async with db.get_session() as session:
        with pytest.raises(ExternalServiceError):
            await dispatcher.Notifier.send_event(
                session, _model(), NotificationEvent(title="dead")
            )
        logs = await _logs(session)
    log = logs[0]
    assert log.status == NotificationLogStatus.FAILED
    assert log.delivered_count == 0
    assert log.target_count == 1
    assert log.targets[0]["error"] == "expired"


@pytest.mark.asyncio
async def test_test_success(db, monkeypatch):
    _patch_channel(monkeypatch, FakeSession(FakeResponse(200, {"ok": True})))
    assert await dispatcher.Notifier.test(_model()) is True


@pytest.mark.asyncio
async def test_test_returns_false_on_transport_error(db, monkeypatch):
    ch = _patch_channel(monkeypatch, FakeSession())
    monkeypatch.setattr(
        ch,
        "test_connection",
        lambda: (_ for _ in ()).throw(requests.ConnectionError("boom")),
    )
    assert await dispatcher.Notifier.test(_model()) is False


@pytest.mark.asyncio
async def test_test_records_a_log_row_when_given_a_session(db, monkeypatch):
    """A probe that found the channel dead has to be visible in the history."""
    ch = _patch_channel(monkeypatch, FakeSession())
    monkeypatch.setattr(ch, "test_connection", lambda: False)
    async with db.get_session() as session:
        assert await dispatcher.Notifier.test(_model(), session) is False
        logs = await _logs(session)
    assert len(logs) == 1
    assert logs[0].trigger == NotificationTrigger.TEST
    assert logs[0].status == NotificationLogStatus.FAILED
    assert logs[0].event_title == dispatcher.CONNECTION_TEST_TITLE


@pytest.mark.asyncio
async def test_test_without_a_session_logs_nothing(db, monkeypatch):
    """Callers that only want the boolean (no DB handy) must stay supported."""
    _patch_channel(monkeypatch, FakeSession(FakeResponse(200, {"ok": True})))
    async with db.get_session() as session:
        assert await dispatcher.Notifier.test(_model()) is True
        assert await _logs(session) == []
