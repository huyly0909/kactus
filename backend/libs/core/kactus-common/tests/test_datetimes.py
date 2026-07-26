"""Tests for the shared UTC/timezone helpers."""

import datetime

from kactus_common.datetimes import VN_TZ, to_utc_naive, utcnow_naive


def test_utcnow_naive_is_naive_and_utc():
    now = utcnow_naive()
    assert now.tzinfo is None
    # Within a wide tolerance of the real UTC clock.
    delta = abs((datetime.datetime.now(datetime.UTC).replace(tzinfo=None) - now))
    assert delta < datetime.timedelta(seconds=5)


def test_to_utc_naive_assumes_vietnam_for_naive_input():
    # Noon in Vietnam is 05:00 UTC.
    vn_noon = datetime.datetime(2026, 7, 26, 12, 0, 0)
    out = to_utc_naive(vn_noon)
    assert out.tzinfo is None
    assert out == datetime.datetime(2026, 7, 26, 5, 0, 0)


def test_to_utc_naive_midnight_vn_rolls_back_a_day():
    # Midnight VN of day D is 17:00 UTC of D-1 — the daily-bar boundary rule.
    vn_midnight = datetime.datetime(2026, 7, 26, 0, 0, 0)
    out = to_utc_naive(vn_midnight)
    assert out == datetime.datetime(2026, 7, 25, 17, 0, 0)


def test_to_utc_naive_converts_aware_input_from_its_own_zone():
    aware = datetime.datetime(2026, 7, 26, 12, 0, 0, tzinfo=VN_TZ)
    assert to_utc_naive(aware) == datetime.datetime(2026, 7, 26, 5, 0, 0)


def test_to_utc_naive_already_utc_is_unchanged():
    aware_utc = datetime.datetime(2026, 7, 26, 5, 0, 0, tzinfo=datetime.UTC)
    assert to_utc_naive(aware_utc) == datetime.datetime(2026, 7, 26, 5, 0, 0)
