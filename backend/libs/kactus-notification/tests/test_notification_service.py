"""Tests for the notification channel service.

In-memory SQLite (OLTP). Settings are registered with a real Fernet key so the
``EncryptedJSON`` config column round-trips (encrypt on write / decrypt on read).

Channels are **project-scoped** now (``ProjectScopedMixin``): the active project
comes from the ``_current_project_id`` ContextVar, is auto-stamped on insert, and
the global SELECT filter enforces the boundary. Tests drive that ContextVar
directly to stand in for "which project the request is in".
"""

from __future__ import annotations

import orjson
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from kactus_common.config import CommonSettings, clear_settings, register_settings
from kactus_common.crypto import CryptoService
from kactus_common.database.oltp.models import Base, utcnow
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.exceptions import NotFoundError, ValidationError
from kactus_common.user.context import set_current_project_id
from kactus_notification.config import NotificationSettings
from kactus_notification.const import (
    NotificationChannelType,
    NotificationLogStatus,
    NotificationTrigger,
)
from kactus_notification.model import NotificationChannel
from kactus_notification.schema import NotificationEvent
from kactus_notification.service import (
    NotificationChannelService,
    NotificationLogService,
)
from sqlalchemy import text

TEST_DB_URL = "sqlite+aiosqlite://"
TEST_KEY = Fernet.generate_key().decode()

TELEGRAM_CFG = {"bot_token": "secret-token", "chat_id": "123456", "parse_mode": "HTML"}


class _Settings(CommonSettings, NotificationSettings):
    """Composite settings, mirroring how kactus-fin merges the two branches.

    The notification code reads from both: ``encryption_key`` lives on the
    kactus-common branch, the retry/zalo knobs on the kactus-notification one.
    Registering a bare ``CommonSettings`` would silently drop the latter
    (``extra="ignore"``) and only blow up at attribute-access time.
    """


@pytest_asyncio.fixture
async def db():
    register_settings(_Settings(encryption_key=TEST_KEY))
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()
    clear_settings()


@pytest.fixture(autouse=True)
def _reset_project_ctx():
    """No project selected by default; clear any test's ctx leakage afterwards."""
    set_current_project_id(None)
    yield
    set_current_project_id(None)


@pytest.mark.asyncio
async def test_create_and_get(db):
    async with db.get_session() as session:
        channel = await NotificationChannelService.create(
            session,
            owner_id=1,
            name="My Bot",
            channel_type=NotificationChannelType.TELEGRAM,
            config=TELEGRAM_CFG,
        )
        assert channel.id is not None
        assert channel.owner_id == 1
        assert channel.channel_type == "telegram"
        # config decrypts back to the original dict after refresh
        assert channel.config["bot_token"] == "secret-token"

        fetched = await NotificationChannelService.get_or_404(
            session, channel_id=channel.id
        )
        assert fetched.id == channel.id


@pytest.mark.asyncio
async def test_project_isolation(db):
    """A channel created in project 1 is invisible from project 2 — 404, no leak."""
    async with db.get_session() as session:
        set_current_project_id(1)
        channel = await NotificationChannelService.create(
            session,
            owner_id=1,
            name="B",
            channel_type=NotificationChannelType.TELEGRAM,
            config=TELEGRAM_CFG,
        )
        assert channel.project_id == 1

        # Another project cannot see it — 404, not a leak.
        set_current_project_id(2)
        with pytest.raises(NotFoundError):
            await NotificationChannelService.get_or_404(session, channel_id=channel.id)

        # …but its own project resolves it.
        set_current_project_id(1)
        assert (
            await NotificationChannelService.get_or_404(session, channel_id=channel.id)
        ).id == channel.id


@pytest.mark.asyncio
async def test_list_for_project_scoped(db):
    async with db.get_session() as session:
        set_current_project_id(1)
        await NotificationChannelService.create(
            session,
            owner_id=1,
            name="A",
            channel_type=NotificationChannelType.TELEGRAM,
            config=TELEGRAM_CFG,
        )
        set_current_project_id(2)
        await NotificationChannelService.create(
            session,
            owner_id=2,
            name="B",
            channel_type=NotificationChannelType.SLACK,
            config={"webhook_url": "https://hooks.slack.com/services/x/y/z"},
        )
        set_current_project_id(1)
        mine = await NotificationChannelService.list_for_project(session)
        assert [c.name for c in mine] == ["A"]


@pytest.mark.asyncio
async def test_update_and_soft_delete(db):
    async with db.get_session() as session:
        channel = await NotificationChannelService.create(
            session,
            owner_id=1,
            name="Old",
            channel_type=NotificationChannelType.TELEGRAM,
            config=TELEGRAM_CFG,
        )
        updated = await NotificationChannelService.update(
            session,
            channel,
            name="New",
            is_active=False,
            config={"bot_token": "t2", "chat_id": "999"},
        )
        assert updated.name == "New"
        assert updated.is_active is False
        assert updated.config["chat_id"] == "999"

        await NotificationChannelService.delete(session, channel)
        assert await NotificationChannelService.list_for_project(session) == []


@pytest.mark.asyncio
async def test_bad_config_raises_validation_error(db):
    async with db.get_session() as session:
        # Missing bot_token / chat_id for a telegram channel.
        with pytest.raises(ValidationError):
            await NotificationChannelService.create(
                session,
                owner_id=1,
                name="bad",
                channel_type=NotificationChannelType.TELEGRAM,
                config={},
            )


@pytest.mark.asyncio
async def test_config_encrypted_at_rest(db):
    """The raw DB column must be ciphertext, not plaintext JSON."""
    async with db.get_session() as session:
        channel = await NotificationChannelService.create(
            session,
            owner_id=1,
            name="Bot",
            channel_type=NotificationChannelType.TELEGRAM,
            config=TELEGRAM_CFG,
        )
        cid = channel.id

    async with db.get_session() as session:
        # text() returns the stored value un-processed (bypasses EncryptedJSON).
        raw = (
            await session.execute(
                text("SELECT config FROM notification_channels WHERE id = :i"),
                {"i": cid},
            )
        ).scalar_one()
        assert isinstance(raw, str)
        assert "secret-token" not in raw  # not stored in the clear
        assert "bot_token" not in raw
        # …but it decrypts back to the original config.
        decrypted = orjson.loads(CryptoService(TEST_KEY).decrypt(raw))
        assert decrypted["bot_token"] == "secret-token"

        # And the ORM round-trip yields the dict again.
        reloaded = await NotificationChannel.get(session, cid)
        assert reloaded.config["chat_id"] == "123456"


# --------------------------------------------------------------------------- #
# NotificationLogService — append-only send audit
# --------------------------------------------------------------------------- #
async def _channel(session, owner_id: int = 1) -> NotificationChannel:
    return await NotificationChannelService.create(
        session,
        owner_id=owner_id,
        name="Bot",
        channel_type=NotificationChannelType.TELEGRAM,
        config=TELEGRAM_CFG,
    )


@pytest.mark.asyncio
async def test_log_record_success(db):
    async with db.get_session() as session:
        channel = await _channel(session)
        log = await NotificationLogService.record(
            session,
            channel=channel,
            event=NotificationEvent(title="Giá vàng", level="warning"),
            status=NotificationLogStatus.SUCCESS,
            attempts=2,
            error=None,
            trigger=NotificationTrigger.MANUAL,
            finished_at=utcnow(),
        )
        assert log.id is not None
        assert log.channel_id == channel.id
        assert log.owner_id == channel.owner_id
        assert log.channel_type == "telegram"
        assert log.event_title == "Giá vàng"
        assert log.level == "warning"
        assert log.status == "success"
        assert log.trigger == "manual"
        assert log.attempts == 2
        assert log.error is None
        assert log.started_at is not None  # aliases create_time


@pytest.mark.asyncio
async def test_log_list_scoped_and_filtered(db):
    async with db.get_session() as session:
        # ch1/ch2 belong to project 1; other belongs to project 2.
        set_current_project_id(1)
        ch1 = await _channel(session, owner_id=1)
        ch2 = await _channel(session, owner_id=1)
        set_current_project_id(2)
        other = await _channel(session, owner_id=2)
        set_current_project_id(None)
        for ch, title in ((ch1, "a"), (ch1, "b"), (ch2, "c"), (other, "d")):
            await NotificationLogService.record(
                session,
                channel=ch,
                event=NotificationEvent(title=title),
                status=NotificationLogStatus.SUCCESS,
                attempts=1,
                error=None,
            )
        # Project-scoped: project 1 sees 3, not project 2's row.
        mine = await NotificationLogService.list_for_project(session, 1)
        assert {log.event_title for log in mine} == {"a", "b", "c"}
        # Channel filter narrows to ch1's two rows.
        ch1_logs = await NotificationLogService.list_for_project(
            session, 1, channel_id=ch1.id
        )
        assert {log.event_title for log in ch1_logs} == {"a", "b"}


@pytest.mark.asyncio
async def test_log_list_limit(db):
    async with db.get_session() as session:
        set_current_project_id(1)
        channel = await _channel(session)
        set_current_project_id(None)
        for i in range(5):
            await NotificationLogService.record(
                session,
                channel=channel,
                event=NotificationEvent(title=f"e{i}"),
                status=NotificationLogStatus.SUCCESS,
                attempts=1,
                error=None,
            )
        limited = await NotificationLogService.list_for_project(session, 1, limit=3)
        assert len(limited) == 3
