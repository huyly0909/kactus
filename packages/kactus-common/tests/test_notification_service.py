"""Tests for the kactus-common notification channel service.

In-memory SQLite (OLTP). Settings are registered with a real Fernet key so the
``EncryptedJSON`` config column round-trips (encrypt on write / decrypt on read).
"""

from __future__ import annotations

import orjson
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from kactus_common.config import CommonSettings, clear_settings, register_settings
from kactus_common.crypto import CryptoService
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.exceptions import NotFoundError, ValidationError
from kactus_common.notification.const import NotificationChannelType
from kactus_common.notification.model import NotificationChannel
from kactus_common.notification.service import NotificationChannelService
from sqlalchemy import text

TEST_DB_URL = "sqlite+aiosqlite://"
TEST_KEY = Fernet.generate_key().decode()

TELEGRAM_CFG = {"bot_token": "secret-token", "chat_id": "123456", "parse_mode": "HTML"}


@pytest_asyncio.fixture
async def db():
    register_settings(CommonSettings(encryption_key=TEST_KEY))
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()
    clear_settings()


@pytest.mark.asyncio
async def test_create_and_get_owned(db):
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

        fetched = await NotificationChannelService.get_owned_or_404(
            session, channel_id=channel.id, owner_id=1
        )
        assert fetched.id == channel.id


@pytest.mark.asyncio
async def test_ownership_isolation(db):
    async with db.get_session() as session:
        channel = await NotificationChannelService.create(
            session, owner_id=1, name="B", channel_type=NotificationChannelType.TELEGRAM,
            config=TELEGRAM_CFG,
        )
        # Another user cannot see it — 404, not a leak.
        with pytest.raises(NotFoundError):
            await NotificationChannelService.get_owned_or_404(
                session, channel_id=channel.id, owner_id=2
            )


@pytest.mark.asyncio
async def test_list_for_owner_scoped(db):
    async with db.get_session() as session:
        await NotificationChannelService.create(
            session, owner_id=1, name="A", channel_type=NotificationChannelType.TELEGRAM,
            config=TELEGRAM_CFG,
        )
        await NotificationChannelService.create(
            session, owner_id=2, name="B", channel_type=NotificationChannelType.SLACK,
            config={"webhook_url": "https://hooks.slack.com/services/x/y/z"},
        )
        mine = await NotificationChannelService.list_for_owner(session, 1)
        assert [c.name for c in mine] == ["A"]


@pytest.mark.asyncio
async def test_update_and_soft_delete(db):
    async with db.get_session() as session:
        channel = await NotificationChannelService.create(
            session, owner_id=1, name="Old", channel_type=NotificationChannelType.TELEGRAM,
            config=TELEGRAM_CFG,
        )
        updated = await NotificationChannelService.update(
            session, channel, name="New", is_active=False,
            config={"bot_token": "t2", "chat_id": "999"},
        )
        assert updated.name == "New"
        assert updated.is_active is False
        assert updated.config["chat_id"] == "999"

        await NotificationChannelService.delete(session, channel)
        assert await NotificationChannelService.list_for_owner(session, 1) == []


@pytest.mark.asyncio
async def test_bad_config_raises_validation_error(db):
    async with db.get_session() as session:
        # Missing bot_token / chat_id for a telegram channel.
        with pytest.raises(ValidationError):
            await NotificationChannelService.create(
                session, owner_id=1, name="bad",
                channel_type=NotificationChannelType.TELEGRAM, config={},
            )


@pytest.mark.asyncio
async def test_config_encrypted_at_rest(db):
    """The raw DB column must be ciphertext, not plaintext JSON."""
    async with db.get_session() as session:
        channel = await NotificationChannelService.create(
            session, owner_id=1, name="Bot",
            channel_type=NotificationChannelType.TELEGRAM, config=TELEGRAM_CFG,
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
