#!/usr/bin/env python3
"""Tests for the MihongGoldSource implementation."""

from datetime import date
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
