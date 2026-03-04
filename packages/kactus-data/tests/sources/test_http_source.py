#!/usr/bin/env python3
"""Tests for the HttpDataSource abstract base class."""

import pytest
from datetime import date, datetime

from kactus_data.schemas import SyncDataResponse


class TestHttpDataSourceABC:
    """Tests for the HttpDataSource abstract base class."""

    def _create_concrete_source(self):
        from kactus_data.sources.http import HttpDataSource

        class TestSource(HttpDataSource):
            def sync(self, start_date, end_date, code):
                return SyncDataResponse(
                    success=True,
                    data_source=self.name,
                    code=code,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    data={"test": True},
                    timestamp=datetime.now().isoformat(),
                )

            def _format_request_date(self, date_obj, is_end_date=False):
                return date_obj.isoformat()

            def _get_headers(self):
                return {"Authorization": "Bearer test"}

            def _get_cookies(self):
                return {}

        return TestSource

    def test_cannot_instantiate_abstract(self):
        from kactus_data.sources.http import HttpDataSource
        with pytest.raises(TypeError):
            HttpDataSource("http://example.com", "test")

    def test_concrete_implementation(self):
        TestSource = self._create_concrete_source()
        source = TestSource("http://example.com/api", "test_source")
        assert source.base_url == "http://example.com/api"
        assert source.name == "test_source"

    def test_sync_returns_response(self):
        TestSource = self._create_concrete_source()
        source = TestSource("http://example.com/api", "test_source")
        result = source.sync(date(2024, 1, 1), date(2024, 1, 31), "SJC")
        assert isinstance(result, SyncDataResponse)
        assert result.success is True
        assert result.data_source == "test_source"

    def test_headers_and_cookies(self):
        TestSource = self._create_concrete_source()
        source = TestSource("http://example.com/api", "test_source")
        assert source._get_headers() == {"Authorization": "Bearer test"}
        assert source._get_cookies() == {}
