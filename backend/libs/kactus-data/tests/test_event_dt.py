"""Tests for the ``event_dt`` derivation helpers."""

import datetime

import pandas as pd
from kactus_data.util.time import to_event_dt, to_event_dt_series


def test_scalar_intraday_shifts_minus_seven_hours():
    # A VN intraday instant becomes the same instant in UTC (−7h).
    out = to_event_dt("2026-07-26 09:30:00")
    assert out == datetime.datetime(2026, 7, 26, 2, 30, 0)
    assert out.tzinfo is None


def test_scalar_calendar_date_is_midnight_vn_to_utc():
    # A bare trading day D → midnight VN → 17:00 UTC of D-1.
    out = to_event_dt(datetime.date(2026, 7, 26))
    assert out == datetime.datetime(2026, 7, 25, 17, 0, 0)


def test_scalar_dayfirst_string():
    out = to_event_dt("26/07/2026 09:30:00", dayfirst=True)
    assert out == datetime.datetime(2026, 7, 26, 2, 30, 0)


def test_scalar_bad_input_is_none():
    assert to_event_dt(None) is None
    assert to_event_dt("not-a-date") is None
    assert to_event_dt(float("nan")) is None


def test_scalar_aware_input_uses_own_zone():
    out = to_event_dt("2026-07-26T09:30:00+00:00")
    assert out == datetime.datetime(2026, 7, 26, 9, 30, 0)


def test_series_roundtrips_back_to_vn_day():
    dates = pd.Series(["2026-07-26", "2026-07-27"])
    ev = to_event_dt_series(dates)
    assert ev.dt.tz is None
    assert ev.iloc[0] == pd.Timestamp("2026-07-25 17:00:00")
    # Converting back to VN restores the original calendar day.
    back = ev.dt.tz_localize("UTC").dt.tz_convert("Asia/Ho_Chi_Minh").dt.date
    assert str(back.iloc[0]) == "2026-07-26"


def test_series_bad_entry_becomes_nat():
    ev = to_event_dt_series(pd.Series(["2026-07-26 09:30:00", "garbage"]))
    assert ev.iloc[0] == pd.Timestamp("2026-07-26 02:30:00")
    assert pd.isna(ev.iloc[1])
