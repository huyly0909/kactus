"""Tests for the gold sync-job contract builders (pure functions, no I/O)."""

from __future__ import annotations

import datetime

import pytest
from kactus_gold.const import GoldJobType
from kactus_gold.schema import GoldScheduleSchema
from kactus_gold.sync import (
    GOLD_BACKFILL_MIN,
    MIHONG_BACKFILL_DAYS,
    GoldBackfillRequest,
    gold_backfill_dedup_key,
    gold_backfill_min,
    gold_sync_dedup_key,
)


def test_job_type_wire_values_unchanged():
    """The enum moved packages; the DB/wire strings must not have moved."""
    assert GoldJobType.GOLD_BACKFILL == "gold_backfill"
    assert GoldJobType.GOLD_SYNC == "gold_sync"


def test_backfill_min_fixed_sources():
    assert gold_backfill_min("sjc") == GOLD_BACKFILL_MIN["sjc"]
    assert gold_backfill_min("yahoo") == datetime.date(2000, 8, 30)


def test_backfill_min_mihong_trails_today():
    """Mihong has no fixed floor — it trails ``today`` by the window length."""
    today = datetime.date(2026, 7, 27)
    assert gold_backfill_min("mihong", today=today) == today - datetime.timedelta(
        days=MIHONG_BACKFILL_DAYS
    )


def test_dedup_keys():
    assert gold_backfill_dedup_key("sjc") == "gold_backfill:sjc"
    assert gold_backfill_dedup_key("mihong", "999") == "gold_backfill:mihong:999"
    assert gold_sync_dedup_key("all") == "gold_sync:all"


def test_backfill_request_rejects_inverted_range():
    with pytest.raises(ValueError):
        GoldBackfillRequest(
            source="sjc",
            date_from=datetime.date(2026, 1, 2),
            date_to=datetime.date(2026, 1, 1),
        )


def test_schedule_schema_defaults_holidays_empty():
    s = GoldScheduleSchema(
        source="sjc",
        code="SJC",
        expected_weekdays=[0, 1, 2, 3, 4],
        timezone="Asia/Ho_Chi_Minh",
        enabled=True,
    )
    assert s.holidays == []
