"""Tests for the gold availability schedule riding the global-settings service.

In-memory SQLite (aiosqlite). Exercises the resolution order (stored row →
lazy default → NotFoundError), config validation on upsert, and the
unknown-entity-type guard — through the gold schema kactus_gold registers.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.exceptions import ConfigurationError, ValidationError
from kactus_common.settings.service import GlobalSettingsService
from kactus_gold.const import GOLD_AVAILABILITY_SCHEDULE
from kactus_gold.schedule import GoldScheduleConfig

TEST_DB_URL = "sqlite+aiosqlite://"

GOLD = GOLD_AVAILABILITY_SCHEDULE


@pytest_asyncio.fixture
async def db():
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()


@pytest.mark.asyncio
async def test_load_uses_registered_default_when_no_row(db):
    """A known series with no stored row resolves the lazy per-series default."""
    async with db.get_session() as session:
        cfg = await GlobalSettingsService.load(
            session, entity_type=GOLD, entity_id="yahoo:XAU"
        )
        assert isinstance(cfg, GoldScheduleConfig)
        assert cfg.timezone == "UTC"  # XAU default is UTC
        assert cfg.expected_weekdays == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_load_unknown_series_falls_back_to_schema_defaults(db):
    """An unknown entity_id still validates ({} → all schema defaults, ICT)."""
    async with db.get_session() as session:
        cfg = await GlobalSettingsService.load(
            session, entity_type=GOLD, entity_id="sjc:UNKNOWN"
        )
        assert cfg.timezone == "Asia/Ho_Chi_Minh"
        assert cfg.enabled is True


@pytest.mark.asyncio
async def test_upsert_then_load_returns_stored_row(db):
    """A stored row overrides the default and round-trips through validation."""
    async with db.get_session() as session:
        await GlobalSettingsService.upsert(
            session,
            entity_type=GOLD,
            entity_id="yahoo:XAU",
            config={"expected_weekdays": [0, 2, 4], "timezone": "Asia/Ho_Chi_Minh"},
        )
        cfg = await GlobalSettingsService.load(
            session, entity_type=GOLD, entity_id="yahoo:XAU"
        )
        assert cfg.expected_weekdays == [0, 2, 4]
        assert cfg.timezone == "Asia/Ho_Chi_Minh"  # overrode the UTC default


@pytest.mark.asyncio
async def test_upsert_updates_single_row(db):
    """A second upsert mutates the same row, not a duplicate."""
    async with db.get_session() as session:
        first = await GlobalSettingsService.upsert(
            session, entity_type=GOLD, entity_id="sjc:SJC", config={"enabled": True}
        )
        second = await GlobalSettingsService.upsert(
            session, entity_type=GOLD, entity_id="sjc:SJC", config={"enabled": False}
        )
        assert first.id == second.id
        cfg = await GlobalSettingsService.load(
            session, entity_type=GOLD, entity_id="sjc:SJC"
        )
        assert cfg.enabled is False


@pytest.mark.asyncio
async def test_upsert_rejects_bad_config(db):
    """An out-of-range weekday / bad timezone is a 400 ValidationError."""
    async with db.get_session() as session:
        with pytest.raises(ValidationError):
            await GlobalSettingsService.upsert(
                session,
                entity_type=GOLD,
                entity_id="sjc:SJC",
                config={"expected_weekdays": [9]},
            )
        with pytest.raises(ValidationError):
            await GlobalSettingsService.upsert(
                session,
                entity_type=GOLD,
                entity_id="sjc:SJC",
                config={"timezone": "America/New_York"},
            )


@pytest.mark.asyncio
async def test_load_unknown_entity_type_raises_configuration_error(db):
    """An unregistered entity type is a misconfiguration, not a 404."""
    async with db.get_session() as session:
        with pytest.raises(ConfigurationError):
            await GlobalSettingsService.load(
                session, entity_type="not_registered", entity_id="x"
            )


@pytest.mark.asyncio
async def test_get_row_none_when_unset(db):
    async with db.get_session() as session:
        assert await GlobalSettingsService.get_row(session, GOLD, "mihong:999") is None
