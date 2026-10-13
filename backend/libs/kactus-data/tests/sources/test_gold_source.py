#!/usr/bin/env python3
"""Tests for the MihongGoldSource implementation."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests
from kactus_data.sources.gold.mihong import (
    CHI_TO_LUONG,
    SUPPORTED_CODES,
    MihongGoldSource,
)


class TestMihongGoldSource:
    """Tests for the MihongGoldSource implementation."""

    def test_initialization(self):
        source = MihongGoldSource()
        assert source.name == "mihong"
        # Must point at the live API host, not the dead www SPA endpoint.
        assert source.base_url == "https://api.mihong.vn/v1/gold-prices"

    def test_accepts_legacy_token_argument(self):
        """kactus-fin still passes a token through; it must not break."""
        assert MihongGoldSource(xsrf_token="legacy").xsrf_token == "legacy"

    def test_headers(self):
        headers = MihongGoldSource()._get_headers()
        assert "referer" in headers
        assert headers["x-market"] == "mihong"

    def test_cookies_empty(self):
        """The endpoint is unauthenticated — no XSRF cookie is sent."""
        assert MihongGoldSource()._get_cookies() == {}

    def test_window_for_same_day_is_intraday(self):
        """A same-day crawl must use 24h so the newest tick is the current price."""
        today = date(2026, 7, 24)
        assert MihongGoldSource._window_for(today, today) == "24h"

    def test_window_for_ranges(self):
        start = date(2026, 1, 1)
        assert MihongGoldSource._window_for(start, date(2026, 1, 10)) == "15d"
        assert MihongGoldSource._window_for(start, date(2026, 1, 25)) == "1M"
        assert MihongGoldSource._window_for(start, date(2026, 5, 1)) == "6M"
        assert MihongGoldSource._window_for(start, date(2026, 12, 31)) == "1y"

    def test_supported_codes(self):
        """DOJI/PNJ/24K are rejected by the API with HTTP 400."""
        assert {"SJC", "999"} <= SUPPORTED_CODES
        assert "DOJI" not in SUPPORTED_CODES
        assert "24K" not in SUPPORTED_CODES

    def test_chi_to_luong_scale(self):
        assert CHI_TO_LUONG == 10

    @patch("kactus_data.sources.gold.mihong.HttpDataSource._make_request")
    def test_sync_success(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "buyingPrice": 13657142,
                "sellingPrice": 13914285,
                "code": "SJC",
                "dateTime": "23/07/2026 00:00",
            }
        ]
        mock_request.return_value = mock_response

        source = MihongGoldSource()
        result = source.sync(date(2026, 7, 24), date(2026, 7, 24), "SJC")

        assert result.success is True
        assert result.data_source == "mihong"
        assert result.code == "SJC"
        assert result.data[0]["buyingPrice"] == 13657142

    @patch("kactus_data.sources.gold.mihong.HttpDataSource._make_request")
    def test_sync_sends_last_window_not_date_range(self, mock_request):
        """Regression: the startDate/endDate form always returns [] now."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_request.return_value = mock_response

        today = date(2026, 7, 24)
        MihongGoldSource().sync(today, today, "SJC")

        _url, params = mock_request.call_args[0]
        assert params == {"market": "domestic", "goldCode": "SJC", "last": "24h"}
        assert "startDate" not in params and "endDate" not in params

    @patch("kactus_data.sources.gold.mihong.HttpDataSource._make_request")
    def test_sync_failure_returns_error(self, mock_request):
        mock_request.side_effect = requests.RequestException("boom")

        result = MihongGoldSource().sync(date(2026, 7, 24), date(2026, 7, 24), "SJC")

        assert result.success is False
        assert "boom" in str(result.error)


# Real api.mihong.vn 6M response for goldCode=999 (end-of-month points), VND/chỉ.
MIHONG_6M_999 = [
    {
        "buyingPrice": 18033469,
        "sellingPrice": 18247959,
        "code": "999",
        "dateTime": "31/12/2025 00:00",
    },
    {
        "buyingPrice": 17699836,
        "sellingPrice": 17941311,
        "code": "999",
        "dateTime": "31/01/2026 00:00",
    },
    {
        "buyingPrice": 17459019,
        "sellingPrice": 17694183,
        "code": "999",
        "dateTime": "28/02/2026 00:00",
    },
    {
        "buyingPrice": 16980050,
        "sellingPrice": 17160304,
        "code": "999",
        "dateTime": "31/03/2026 00:00",
    },
]


def _mock_request(mock_request, payload):
    response = MagicMock()
    response.json.return_value = payload
    mock_request.return_value = response


class TestMihongGoldHistory:
    @patch("kactus_data.sources.gold.mihong.HttpDataSource._make_request")
    def test_parses_full_array_and_scales_to_luong(self, mock_request):
        """Every point is parsed (not just the last), VND/chỉ ×10 → VND/lượng."""
        _mock_request(mock_request, MIHONG_6M_999)

        rows = MihongGoldSource().history(date(2025, 12, 1), date(2026, 3, 31), "999")

        assert [r["date"] for r in rows] == [
            date(2025, 12, 31),
            date(2026, 1, 31),
            date(2026, 2, 28),
            date(2026, 3, 31),
        ]
        # 18_033_469 chỉ × 10 = 180_334_690 lượng, as an exact Decimal.
        assert rows[0]["buy_price"] == Decimal("180334690.0000")
        assert rows[0]["sell_price"] == Decimal("182479590.0000")
        assert all(isinstance(r["buy_price"], Decimal) for r in rows)

    @patch("kactus_data.sources.gold.mihong.HttpDataSource._make_request")
    def test_monthly_points_beyond_a_month(self, mock_request):
        """A >1-month range yields the API's end-of-month granularity, kept verbatim."""
        _mock_request(mock_request, MIHONG_6M_999)
        rows = MihongGoldSource().history(date(2025, 12, 1), date(2026, 3, 31), "999")
        # Consecutive points are ~a month apart — not daily.
        gaps = [(b["date"] - a["date"]).days for a, b in zip(rows, rows[1:])]
        assert all(gap >= 28 for gap in gaps)

    @patch("kactus_data.sources.gold.mihong.HttpDataSource._make_request")
    def test_clips_to_requested_range(self, mock_request):
        """The trailing last= window can be wider than asked — points are clipped."""
        _mock_request(mock_request, MIHONG_6M_999)
        rows = MihongGoldSource().history(date(2026, 1, 1), date(2026, 2, 28), "999")
        assert [r["date"] for r in rows] == [date(2026, 1, 31), date(2026, 2, 28)]

    @patch("kactus_data.sources.gold.mihong.HttpDataSource._make_request")
    def test_daily_points_within_a_month(self, mock_request):
        """15d/1M windows return consecutive daily points; all are kept."""
        payload = [
            {
                "buyingPrice": 1_000_000 + i,
                "sellingPrice": 1_100_000 + i,
                "code": "999",
                "dateTime": f"{day:02d}/03/2026 09:00",
            }
            for i, day in enumerate(range(1, 6))
        ]
        _mock_request(mock_request, payload)
        rows = MihongGoldSource().history(date(2026, 3, 1), date(2026, 3, 5), "999")
        assert [r["date"] for r in rows] == [date(2026, 3, d) for d in range(1, 6)]

    @patch("kactus_data.sources.gold.mihong.HttpDataSource._make_request")
    def test_failed_fetch_returns_empty(self, mock_request):
        mock_request.side_effect = requests.RequestException("boom")
        assert (
            MihongGoldSource().history(date(2026, 1, 1), date(2026, 3, 1), "999") == []
        )
