"""Gold data-availability schedule — the first ``global_settings`` consumer.

Declares *when* each gold series is expected to have data, so the UI can flag a
hole ("gap") or a stale latest row ("no data today"). Pure OLTP config (weekday
numbers + holiday calendar dates + a timezone label) — no DuckDB, no instants.
The generic machinery (table, registry, service) stays in
``kactus_common.settings``; this module registers the gold schema into it.

The ``timezone`` is the *market's operating zone* (which calendar day counts as a
trading day / what "today" means), distinct from the viewer's display timezone.
Only ``UTC`` and ``Asia/Ho_Chi_Minh`` (ICT, UTC+7) are supported for now.
"""

from __future__ import annotations

import datetime
from typing import Literal

from kactus_common.schemas import BaseSchema
from kactus_common.settings.registry import register_settings_schema
from pydantic import field_validator

from .const import GOLD_AVAILABILITY_SCHEDULE

#: Supported schedule timezones (constrained until more are needed).
ScheduleTimezone = Literal["UTC", "Asia/Ho_Chi_Minh"]
SUPPORTED_SCHEDULE_TIMEZONES: tuple[ScheduleTimezone, ...] = ("UTC", "Asia/Ho_Chi_Minh")
#: Default is the local (Vietnam) zone.
DEFAULT_SCHEDULE_TIMEZONE: ScheduleTimezone = "Asia/Ho_Chi_Minh"


class GoldScheduleConfig(BaseSchema):
    """When a gold source is expected to have data.

    ``expected_weekdays`` uses Python's ``date.weekday()`` encoding: Mon=0 … Sun=6.
    ``holidays`` are calendar dates (interpreted in ``timezone``) with no data.
    """

    expected_weekdays: list[int] = [0, 1, 2, 3, 4]  # Mon–Fri by default
    holidays: list[datetime.date] = []
    timezone: ScheduleTimezone = DEFAULT_SCHEDULE_TIMEZONE
    enabled: bool = True
    # NOTE: a `notify` block (alert when a gap/today-missing appears) is deferred;
    # add it here later without touching the table or the registry.

    @field_validator("expected_weekdays")
    @classmethod
    def _valid_weekdays(cls, v: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("expected_weekdays must be 0–6 (Mon=0 … Sun=6)")
        return sorted(set(v))


def gold_schedule_entity_id(source: str, code: str) -> str:
    """The settings ``entity_id`` for one gold series (source disambiguates 999)."""
    return f"{source}:{code}"


#: Per-series defaults, so the chips work before any admin writes a row. World
#: spot (Yahoo XAU) is anchored to UTC; domestic series to ICT. Mihong (dealer)
#: quotes every day; SJC follows business days.
DEFAULT_GOLD_SCHEDULES: dict[str, dict] = {
    "yahoo:XAU": {"expected_weekdays": [0, 1, 2, 3, 4], "timezone": "UTC"},
    "sjc:SJC": {"expected_weekdays": [0, 1, 2, 3, 4], "timezone": "Asia/Ho_Chi_Minh"},
    "sjc:999": {"expected_weekdays": [0, 1, 2, 3, 4], "timezone": "Asia/Ho_Chi_Minh"},
    "mihong:999": {
        "expected_weekdays": [0, 1, 2, 3, 4, 5, 6],
        "timezone": "Asia/Ho_Chi_Minh",
    },
}


def _default_gold_schedule(entity_id: str) -> dict:
    """Lazy default for a series with no stored row ({} → all-defaults)."""
    return DEFAULT_GOLD_SCHEDULES.get(entity_id, {})


register_settings_schema(
    GOLD_AVAILABILITY_SCHEDULE,
    GoldScheduleConfig,
    default_factory=_default_gold_schedule,
)
