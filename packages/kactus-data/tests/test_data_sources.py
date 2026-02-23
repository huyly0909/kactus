#!/usr/bin/env python3
"""
Tests for kactus-data package: schemas, data sources, and cross-package imports.
"""

import pytest
from datetime import date, datetime
from typing import Dict
from unittest.mock import patch, MagicMock


class TestImports:
    """Verify all kactus-data modules import correctly."""

    def test_import_package(self):
        """Test top-level package import."""
        import kactus_data
        assert kactus_data is not None

    def test_import_schemas(self):
        """Test schemas module import."""
        from kactus_data.schemas.data_source import SyncDataResponse
        assert SyncDataResponse is not None

    def test_import_sources_base(self):
        """Test DataSource ABC import."""
        from kactus_data.sources.base import DataSource
        assert DataSource is not None

    def test_import_sources_mihong(self):
        """Test MihongDataSource import."""
        from kactus_data.sources.mihong import MihongDataSource
        assert MihongDataSource is not None

    def test_import_jobs(self):
        """Test jobs module import."""
        import kactus_data.jobs
        assert kactus_data.jobs is not None

    def test_cross_package_import_kactus_common(self):
        """Test that kactus-common is accessible from kactus-data."""
        from kactus_common.database.duckdb.client import DatabaseClient
        from kactus_common.database.duckdb.schema import Table, Column
        from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
        assert DatabaseClient is not None
        assert Table is not None


class TestSyncDataResponse:
    """Tests for the SyncDataResponse Pydantic model."""

    def test_create_success_response(self):
        """Test creating a successful sync response."""
        response = SyncDataResponse(
            success=True,
            data_source="test_source",
            code="SJC",
            start_date="2024-01-01",
            end_date="2024-01-31",
            data={"prices": [100, 200]},
            timestamp="2024-01-31T12:00:00",
        )
        assert response.success is True
        assert response.data_source == "test_source"
        assert response.code == "SJC"
        assert response.data == {"prices": [100, 200]}
        assert response.error is None

    def test_create_error_response(self):
        """Test creating an error sync response."""
        response = SyncDataResponse(
            success=False,
            data_source="test_source",
            code="SJC",
            start_date="2024-01-01",
            end_date="2024-01-31",
            error="Connection timeout",
            timestamp="2024-01-31T12:00:00",
        )
        assert response.success is False
        assert response.error == "Connection timeout"
        assert response.data is None

    def test_error_as_dict(self):
        """Test error field accepts dict."""
        response = SyncDataResponse(
            success=False,
            data_source="test_source",
            code="SJC",
            start_date="2024-01-01",
            end_date="2024-01-31",
            error={"message": "Failed", "status_code": 500},
            timestamp="2024-01-31T12:00:00",
        )
        assert isinstance(response.error, dict)
        assert response.error["status_code"] == 500

    def test_serialization(self):
        """Test model serialization to dict."""
        response = SyncDataResponse(
            success=True,
            data_source="mihong",
            code="999",
            start_date="2024-01-01",
            end_date="2024-01-31",
            data={},
            timestamp="2024-01-31T12:00:00",
        )
        data = response.model_dump()
        assert data["success"] is True
        assert data["data_source"] == "mihong"


# Import here so the schema tests can reference it
from kactus_data.schemas.data_source import SyncDataResponse


class TestDataSourceABC:
    """Tests for the DataSource abstract base class."""

    def _create_concrete_source(self):
        """Create a concrete implementation for testing."""
        from kactus_data.sources.base import DataSource

        class TestSource(DataSource):
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
        """Test that DataSource cannot be instantiated directly."""
        from kactus_data.sources.base import DataSource
        with pytest.raises(TypeError):
            DataSource("http://example.com", "test")

    def test_concrete_implementation(self):
        """Test a concrete DataSource implementation."""
        TestSource = self._create_concrete_source()
        source = TestSource("http://example.com/api", "test_source")
        assert source.base_url == "http://example.com/api"
        assert source.name == "test_source"

    def test_sync_returns_response(self):
        """Test that sync returns a SyncDataResponse."""
        TestSource = self._create_concrete_source()
        source = TestSource("http://example.com/api", "test_source")
        result = source.sync(date(2024, 1, 1), date(2024, 1, 31), "SJC")
        assert isinstance(result, SyncDataResponse)
        assert result.success is True
        assert result.data_source == "test_source"

    def test_headers_and_cookies(self):
        """Test that headers and cookies are returned correctly."""
        TestSource = self._create_concrete_source()
        source = TestSource("http://example.com/api", "test_source")
        assert source._get_headers() == {"Authorization": "Bearer test"}
        assert source._get_cookies() == {}


class TestMihongDataSource:
    """Tests for the MihongDataSource implementation."""

    def test_initialization(self):
        """Test MihongDataSource initializes with correct defaults."""
        from kactus_data.sources.mihong import MihongDataSource
        source = MihongDataSource(xsrf_token="test-token")
        assert source.name == "mihong"
        assert "mihong.vn" in source.base_url
        assert source.xsrf_token == "test-token"

    def test_headers(self):
        """Test MihongDataSource returns correct headers."""
        from kactus_data.sources.mihong import MihongDataSource
        source = MihongDataSource(xsrf_token="test-token")
        headers = source._get_headers()
        assert "referer" in headers
        assert "x-requested-with" in headers

    def test_cookies(self):
        """Test MihongDataSource returns correct cookies."""
        from kactus_data.sources.mihong import MihongDataSource
        source = MihongDataSource(xsrf_token="my-xsrf-token")
        cookies = source._get_cookies()
        assert cookies["XSRF-TOKEN"] == "my-xsrf-token"

    def test_format_start_date(self):
        """Test date formatting for start dates."""
        from kactus_data.sources.mihong import MihongDataSource
        source = MihongDataSource(xsrf_token="test")
        formatted = source._format_request_date(date(2024, 1, 5), is_end_date=False)
        assert "1/5/2024" in formatted
        assert "00:00:00" in formatted

    def test_format_end_date(self):
        """Test date formatting for end dates."""
        from kactus_data.sources.mihong import MihongDataSource
        source = MihongDataSource(xsrf_token="test")
        formatted = source._format_request_date(date(2024, 12, 25), is_end_date=True)
        assert "12/25/2024" in formatted
        assert "23:59:59" in formatted

    @patch("kactus_data.sources.mihong.DataSource._make_request")
    def test_sync_success(self, mock_request):
        """Test successful sync call."""
        from kactus_data.sources.mihong import MihongDataSource

        mock_response = MagicMock()
        mock_response.json.return_value = {"prices": [{"date": "2024-01-01", "price": 72.5}]}
        mock_request.return_value = mock_response

        source = MihongDataSource(xsrf_token="test")
        result = source.sync(date(2024, 1, 1), date(2024, 1, 31), "SJC")

        assert result.success is True
        assert result.data_source == "mihong"
        assert result.code == "SJC"
        assert result.data is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
