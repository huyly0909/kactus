"""Gold sync-job contract — request schemas + dedup/param builders.

The gold *handlers* live in kactus-data (the data plane), but two different
processes enqueue gold jobs: the kactus-fin admin API (a superuser click) and
the kactus-data CLI (local debug). kactus-fin may not import kactus-data, so the
shared shape of a gold job — the request body, the ``params`` dict keys the
handler reads, its ``dedup_key``, and each source's earliest backfill date —
lives here in kactus-common, where both sides reach it and neither can drift.
"""

from __future__ import annotations

import datetime
from enum import StrEnum

from kactus_common.schemas import BaseSchema
from pydantic import model_validator


class GoldSource(StrEnum):
    """A backfillable gold data source (the sync-now target adds ``all``)."""

    SJC = "sjc"
    YAHOO = "yahoo"
    MIHONG = "mihong"


#: Earliest date each source can backfill — the ``all`` lower bound. Mihong is a
#: trailing ~1-year window with no fixed floor, so it is resolved per-request
#: from :data:`MIHONG_BACKFILL_DAYS` (see :func:`gold_backfill_min`).
GOLD_BACKFILL_MIN: dict[str, datetime.date] = {
    GoldSource.SJC: datetime.date(2009, 7, 22),
    GoldSource.YAHOO: datetime.date(2000, 8, 30),
}

#: How far back Mihong's trailing window reaches (its dynamic backfill floor).
MIHONG_BACKFILL_DAYS = 365

#: The market's local zone — "today" for a trailing window is the VN calendar
#: day, never the (possibly UTC) server day.
_VN_TZ = datetime.timezone(datetime.timedelta(hours=7))


def vn_today() -> datetime.date:
    """The current calendar date in Vietnam (source feeds' local zone)."""
    return datetime.datetime.now(_VN_TZ).date()


def gold_backfill_min(
    source: str, *, today: datetime.date | None = None
) -> datetime.date:
    """The earliest date ``source`` can backfill, as of ``today`` (VN)."""
    fixed = GOLD_BACKFILL_MIN.get(source)
    if fixed is not None:
        return fixed
    return (today or vn_today()) - datetime.timedelta(days=MIHONG_BACKFILL_DAYS)


def gold_backfill_dedup_key(source: str, code: str | None = None) -> str:
    """Collapse duplicate backfills: one live job per ``(source[, code])``."""
    return f"gold_backfill:{source}:{code}" if code else f"gold_backfill:{source}"


def gold_sync_dedup_key(source: str) -> str:
    """Collapse duplicate sync-nows: one live job per source (``all`` is a key)."""
    return f"gold_sync:{source}"


class GoldBackfillRequest(BaseSchema):
    """Backfill one gold series over a date range (superuser)."""

    source: GoldSource
    #: Domestic code override (Mihong only, e.g. ``999``); SJC/Yahoo force theirs.
    code: str | None = None
    date_from: datetime.date
    date_to: datetime.date

    @model_validator(mode="after")
    def _check_range(self) -> GoldBackfillRequest:
        if self.date_from > self.date_to:
            raise ValueError("date_from must be on or before date_to")
        return self


class GoldSyncRequest(BaseSchema):
    """Fetch current gold quotes now — board refresh + intraday tick log."""

    #: ``all`` (default) or one of ``sjc`` / ``mihong`` / ``yahoo``.
    source: str = "all"
