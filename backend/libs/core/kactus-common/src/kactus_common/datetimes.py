"""Timezone helpers shared by both the OLTP and OLAP layers.

Two storage conventions live side by side in this codebase:

- **OLTP (Postgres)** columns are ``TIMESTAMPTZ`` (see
  :class:`kactus_common.database.oltp.types.DateTimeTzAware`) and hold
  timezone-aware UTC — use :func:`kactus_common.database.oltp.models.utcnow`.
- **OLAP (DuckDB)** columns are naive ``TIMESTAMP`` with no zone. The
  convention there is *naive UTC wall-clock*: the stored value is always UTC,
  the ``tzinfo`` is simply dropped because the column cannot carry it. The
  helpers below produce exactly that.

For OLAP business tables the source timestamp (Vietnam local / a calendar day)
is kept verbatim in its native column, and a derived UTC instant is written to
the reserved ``event_dt`` column — the single, canonical UTC axis used for
filtering and cross-source sync. ``event_dt`` is always naive UTC.
"""

from __future__ import annotations

import datetime

#: The market's local zone. Most Vietnamese source feeds (vnstock, PNJ) emit
#: naive local time in this zone; converting it is what yields a UTC instant.
VN_TZ = datetime.timezone(datetime.timedelta(hours=7))


def utcnow_naive() -> datetime.datetime:
    """Current UTC time as a naive ``datetime`` (UTC wall-clock, no tzinfo).

    Use for OLAP ``TIMESTAMP`` columns (audit stamps like ``crawled_at`` /
    ``synced_at`` / ``imported_at``). For OLTP use ``utcnow`` instead — that
    keeps the ``tzinfo`` the ``TIMESTAMPTZ`` column needs.
    """
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def to_utc_naive(
    dt: datetime.datetime,
    assume_tz: datetime.tzinfo = VN_TZ,
) -> datetime.datetime:
    """Normalize a datetime to naive UTC wall-clock.

    A naive input is assumed to be in ``assume_tz`` (Vietnam by default, since
    that is what the source feeds carry). An aware input is converted from its
    own zone. The returned value is always naive UTC — ready for a DuckDB
    ``TIMESTAMP`` column.
    """
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=assume_tz)
    return dt.astimezone(datetime.UTC).replace(tzinfo=None)
