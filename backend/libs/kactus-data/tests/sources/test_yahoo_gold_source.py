"""YahooGoldSource — world gold (XAU/USD) daily bars, no network."""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

import pytest
import requests
from kactus_data.sources.gold.yahoo import CODE, SYMBOL, YahooGoldSource


def _payload(rows: list[tuple[int, float | None]]) -> dict:
    """Build Yahoo's columnar chart shape from (timestamp, close) pairs."""
    return {
        "chart": {
            "result": [
                {
                    "timestamp": [ts for ts, _ in rows],
                    "indicators": {
                        "quote": [
                            {
                                "open": [c for _, c in rows],
                                "high": [c for _, c in rows],
                                "low": [c for _, c in rows],
                                "close": [c for _, c in rows],
                            }
                        ]
                    },
                }
            ]
        }
    }


def _ts(y: int, m: int, d: int) -> int:
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


def _response(payload: dict) -> Mock:
    resp = Mock()
    resp.json.return_value = payload
    return resp


def test_uses_futures_symbol_not_delisted_spot():
    """XAUUSD=X is delisted; GC=F is the working symbol."""
    assert SYMBOL == "GC=F"
    assert CODE == "XAU"


def test_sync_flattens_daily_bars():
    payload = _payload([(_ts(2026, 7, 23), 4020.5), (_ts(2026, 7, 24), 4037.7)])
    with patch.object(
        YahooGoldSource, "_make_request", return_value=_response(payload)
    ):
        resp = YahooGoldSource().sync(date(2026, 7, 23), date(2026, 7, 24))

    assert resp.success
    assert resp.data_source == "yahoo"
    assert resp.code == "XAU"
    assert [b["date"] for b in resp.data] == ["2026-07-23", "2026-07-24"]
    assert resp.data[-1]["close"] == 4037.7


def test_sync_skips_null_padded_non_trading_days():
    """Yahoo pads holidays/weekends with null closes — those are not bars."""
    payload = _payload(
        [
            (_ts(2026, 7, 23), 4020.5),
            (_ts(2026, 7, 24), None),
            (_ts(2026, 7, 25), 4041.0),
        ]
    )
    with patch.object(
        YahooGoldSource, "_make_request", return_value=_response(payload)
    ):
        resp = YahooGoldSource().sync(date(2026, 7, 23), date(2026, 7, 25))

    assert [b["date"] for b in resp.data] == ["2026-07-23", "2026-07-25"]


def test_sync_requests_daily_interval_with_unix_bounds():
    """`range=max` silently degrades to monthly bars — period1/period2 + 1d is required."""
    captured: dict = {}

    def _capture(url, params, **kwargs):
        captured["url"] = url
        captured["params"] = params
        return _response(_payload([(_ts(2026, 7, 24), 4037.7)]))

    with patch.object(YahooGoldSource, "_make_request", side_effect=_capture):
        YahooGoldSource().sync(date(2026, 7, 1), date(2026, 7, 24))

    assert captured["params"]["interval"] == "1d"
    assert "range" not in captured["params"]
    assert captured["params"]["period1"] == str(_ts(2026, 7, 1))
    # The end bound is padded a day so the final session is included.
    assert captured["params"]["period2"] == str(_ts(2026, 7, 24) + 86400)


def test_sync_falls_back_to_second_host():
    """query1 occasionally rejects; the query2 mirror must be tried."""
    calls: list[str] = []

    def _flaky(url, params, **kwargs):
        calls.append(url)
        if "query1" in url:
            raise requests.RequestException("rejected")
        return _response(_payload([(_ts(2026, 7, 24), 4037.7)]))

    with patch.object(YahooGoldSource, "_make_request", side_effect=_flaky):
        resp = YahooGoldSource().sync(date(2026, 7, 24), date(2026, 7, 24))

    assert resp.success
    assert len(calls) == 2 and "query2" in calls[1]


def test_sync_reports_failure_when_every_host_fails():
    with patch.object(
        YahooGoldSource, "_make_request", side_effect=requests.RequestException("down")
    ):
        resp = YahooGoldSource().sync(date(2026, 7, 24), date(2026, 7, 24))

    assert resp.success is False
    assert resp.data == []
    assert "down" in resp.error["message"]


def test_latest_returns_final_bar():
    payload = _payload([(_ts(2026, 7, 23), 4020.5), (_ts(2026, 7, 24), 4037.7)])
    with patch.object(
        YahooGoldSource, "_make_request", return_value=_response(payload)
    ):
        bar = YahooGoldSource().latest()

    assert bar["date"] == "2026-07-24"
    assert bar["close"] == 4037.7


def test_latest_returns_none_when_unavailable():
    with patch.object(
        YahooGoldSource, "_make_request", side_effect=requests.RequestException("down")
    ):
        assert YahooGoldSource().latest() is None


@pytest.mark.parametrize("header", ["user-agent"])
def test_sends_browser_user_agent(header):
    """Yahoo rejects requests without a browser-ish User-Agent."""
    assert header in {k.lower() for k in YahooGoldSource()._get_headers()}
