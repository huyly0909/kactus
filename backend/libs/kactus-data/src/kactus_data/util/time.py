"""Compute the canonical UTC ``event_dt`` for OLAP business rows.

Vietnamese market feeds (vnstock candles, PNJ snapshots, exchange news/events)
emit their timestamps in Vietnam wall-clock — naive local time, or a bare
calendar date meaning "midnight in Vietnam". We keep that native value verbatim
in its own column and derive a single canonical UTC instant into the reserved
``event_dt`` column.

The rule is uniform: **interpret the native value as Vietnam wall-clock, convert
to UTC, drop the tzinfo** (DuckDB ``TIMESTAMP`` is naive). A calendar date is
treated as midnight-in-Vietnam, so a daily bar for day *D* becomes ``D-1 17:00``
UTC — which, converted back to Vietnam for display, is day *D* again. ``event_dt``
is what all time filtering / cross-source sync compares against.
"""

from __future__ import annotations

import datetime

import pandas as pd
from kactus_common.datetimes import VN_TZ


def to_event_dt_series(values: pd.Series, *, dayfirst: bool = False) -> pd.Series:
    """Convert a native Vietnam-local column to a naive-UTC ``event_dt`` series.

    Accepts datetimes, dates, or parseable strings. Naive values are assumed to
    be Vietnam local; already tz-aware values are converted from their own zone.
    Unparseable entries become ``NaT`` (stored as NULL) rather than raising —
    one bad row must not drop a whole crawl.

    ``dayfirst`` matches Vietnamese ``DD/MM/YYYY`` source strings.
    """
    ts = pd.to_datetime(values, errors="coerce", dayfirst=dayfirst)
    if getattr(ts.dtype, "tz", None) is None:
        ts = ts.dt.tz_localize(VN_TZ, ambiguous="NaT", nonexistent="NaT")
    return ts.dt.tz_convert("UTC").dt.tz_localize(None)


def to_event_dt(value: object, *, dayfirst: bool = False) -> datetime.datetime | None:
    """Scalar form of :func:`to_event_dt_series` — native VN value → naive UTC.

    Returns ``None`` for missing/unparseable input (stored as NULL). Use it in
    per-row builders (news / events / foreign-trade) where the native timestamp
    is a free-form source string.
    """
    ts = pd.to_datetime(value, errors="coerce", dayfirst=dayfirst)
    if ts is None or pd.isna(ts):
        return None
    if ts.tzinfo is None:
        ts = ts.tz_localize(VN_TZ)
    return ts.tz_convert("UTC").tz_localize(None).to_pydatetime()
