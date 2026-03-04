#!/usr/bin/env python3
"""Tests for the MihongGoldSource implementation."""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from kactus_data.schemas import SyncDataResponse


class TestMihongGoldSource:
    """Tests for the MihongGoldSource implementation."""

    def test_initialization(self):
        from kactus_data.sources.gold.mihong import MihongGoldSource
        source = MihongGoldSource(xsrf_token="test-token")
        assert source.name == "mihong"
        assert "mihong.vn" in source.base_url
        assert source.xsrf_token == "test-token"

    def test_headers(self):
        from kactus_data.sources.gold.mihong import MihongGoldSource
        source = MihongGoldSource(xsrf_token="test-token")
        headers = source._get_headers()
        assert "referer" in headers
        assert "x-requested-with" in headers

    def test_cookies(self):
        from kactus_data.sources.gold.mihong import MihongGoldSource
        source = MihongGoldSource(xsrf_token="my-xsrf-token")
        cookies = source._get_cookies()
        assert cookies["XSRF-TOKEN"] == "my-xsrf-token"

    def test_format_start_date(self):
        from kactus_data.sources.gold.mihong import MihongGoldSource
        source = MihongGoldSource(xsrf_token="test")
        formatted = source._format_request_date(date(2024, 1, 5), is_end_date=False)
        assert "1/5/2024" in formatted
        assert "00:00:00" in formatted

    def test_format_end_date(self):
        from kactus_data.sources.gold.mihong import MihongGoldSource
        source = MihongGoldSource(xsrf_token="test")
        formatted = source._format_request_date(date(2024, 12, 25), is_end_date=True)
        assert "12/25/2024" in formatted
        assert "23:59:59" in formatted

    @patch("kactus_data.sources.gold.mihong.HttpDataSource._make_request")
    def test_sync_success(self, mock_request):
        from kactus_data.sources.gold.mihong import MihongGoldSource

        mock_response = MagicMock()
        mock_response.json.return_value = {"prices": [{"date": "2024-01-01", "price": 72.5}]}
        mock_request.return_value = mock_response

        source = MihongGoldSource(xsrf_token="test")
        result = source.sync(date(2024, 1, 1), date(2024, 1, 31), "SJC")

        assert result.success is True
        assert result.data_source == "mihong"
        assert result.code == "SJC"
        assert result.data is not None
