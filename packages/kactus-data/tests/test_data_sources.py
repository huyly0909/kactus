#!/usr/bin/env python3
"""Tests for kactus-data package: schemas, sources, storage, pipeline."""

import pytest
from datetime import date, datetime
from unittest.mock import patch, MagicMock

from kactus_data.schemas import SyncDataResponse, SyncResult


class TestImports:
    """Verify all kactus-data modules import correctly."""

    def test_import_package(self):
        import kactus_data
        assert kactus_data is not None

    def test_import_schemas(self):
        from kactus_data.schemas import SyncDataResponse, SyncResult
        assert SyncDataResponse is not None
        assert SyncResult is not None

    def test_import_http_source(self):
        from kactus_data.sources.http import HttpDataSource
        assert HttpDataSource is not None

    def test_import_gold_mihong(self):
        from kactus_data.sources.gold.mihong import MihongGoldSource
        assert MihongGoldSource is not None

    def test_import_gold_package(self):
        from kactus_data.sources.gold import MihongGoldSource
        assert MihongGoldSource is not None

    def test_import_domain_placeholders(self):
        import kactus_data.sources.stock
        import kactus_data.sources.coin
        assert kactus_data.sources.stock is not None
        assert kactus_data.sources.coin is not None

    def test_import_storage(self):
        from kactus_data.storage.duckdb import DuckDBStorage
        assert DuckDBStorage is not None

    def test_import_pipeline(self):
        from kactus_data.pipeline import SyncPipeline
        assert SyncPipeline is not None

    def test_import_jobs(self):
        import kactus_data.jobs
        assert kactus_data.jobs is not None

    def test_cross_package_import_kactus_common(self):
        from kactus_common.database.duckdb.client import DatabaseClient
        from kactus_common.database.duckdb.schema import Table, Column
        from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
        assert DatabaseClient is not None
        assert Table is not None


class TestSyncDataResponse:
    """Tests for the SyncDataResponse schema."""

    def test_create_success_response(self):
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

    def test_inherits_base_schema(self):
        from kactus_common.schemas import BaseSchema
        assert issubclass(SyncDataResponse, BaseSchema)


class TestSyncResult:
    """Tests for SyncResult schema."""

    def test_success_result(self):
        result = SyncResult(
            data_source="mihong",
            rows_fetched=100,
            rows_stored=100,
            table_name="gold_prices",
            duration_ms=1234.5,
            success=True,
        )
        assert result.success is True
        assert result.rows_fetched == 100
        assert result.error is None

    def test_error_result(self):
        result = SyncResult(
            data_source="mihong",
            rows_fetched=0,
            rows_stored=0,
            table_name="gold_prices",
            duration_ms=50.0,
            success=False,
            error="Connection refused",
        )
        assert result.success is False
        assert result.error == "Connection refused"


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


class TestDuckDBStorage:
    """Tests for DuckDBStorage."""

    def test_init(self, tmp_path):
        from kactus_data.storage.duckdb import DuckDBStorage
        db = DuckDBStorage(str(tmp_path / "test.duckdb"))
        assert db.db_path == str(tmp_path / "test.duckdb")
        db.close()

    def test_list_tables_empty(self, tmp_path):
        from kactus_data.storage.duckdb import DuckDBStorage
        db = DuckDBStorage(str(tmp_path / "test.duckdb"))
        tables = db.list_tables()
        assert tables == []
        db.close()

    def test_store_and_list(self, tmp_path):
        import pandas as pd
        from kactus_data.storage.duckdb import DuckDBStorage
        from kactus_common.database.duckdb.schema import Table, Column
        from kactus_common.database.duckdb.consts import DataType, UpdateStrategy

        db = DuckDBStorage(str(tmp_path / "test.duckdb"))
        table = Table(
            name="test_prices",
            columns=[
                Column(name="code", data_type=DataType.STRING),
                Column(name="price", data_type=DataType.FLOAT),
            ],
        )
        df = pd.DataFrame({"code": ["SJC", "999"], "price": [72.5, 73.0]})
        rows = db.store(table, df, UpdateStrategy.REPLACE)
        assert rows == 2
        assert "test_prices" in db.list_tables()
        db.close()

    def test_query(self, tmp_path):
        import pandas as pd
        from kactus_data.storage.duckdb import DuckDBStorage
        from kactus_common.database.duckdb.schema import Table, Column
        from kactus_common.database.duckdb.consts import DataType, UpdateStrategy

        db = DuckDBStorage(str(tmp_path / "test.duckdb"))
        table = Table(
            name="prices",
            columns=[
                Column(name="code", data_type=DataType.STRING),
                Column(name="price", data_type=DataType.FLOAT),
            ],
        )
        df = pd.DataFrame({"code": ["SJC"], "price": [72.5]})
        db.store(table, df, UpdateStrategy.REPLACE)

        result = db.query("SELECT * FROM prices")
        assert len(result) == 1
        assert result.iloc[0]["code"] == "SJC"
        db.close()

    def test_export_table(self, tmp_path):
        import pandas as pd
        from kactus_data.storage.duckdb import DuckDBStorage
        from kactus_common.database.duckdb.schema import Table, Column
        from kactus_common.database.duckdb.consts import DataType, UpdateStrategy

        db = DuckDBStorage(str(tmp_path / "test.duckdb"))
        table = Table(
            name="prices",
            columns=[Column(name="code", data_type=DataType.STRING)],
        )
        db.store(table, pd.DataFrame({"code": ["SJC"]}), UpdateStrategy.REPLACE)

        output_dir = str(tmp_path / "backups")
        path = db.export_table("prices", output_dir, "parquet")
        assert path.endswith(".parquet")
        assert "prices" in path
        import os
        assert os.path.exists(path)
        db.close()


class TestSyncPipeline:
    """Tests for SyncPipeline."""

    def test_pipeline_success(self, tmp_path):
        import pandas as pd
        from kactus_data.pipeline import SyncPipeline
        from kactus_data.storage.duckdb import DuckDBStorage
        from kactus_common.database.duckdb.schema import Table, Column
        from kactus_common.database.duckdb.consts import DataType

        # Create a mock source
        from kactus_data.sources.http import HttpDataSource

        class FakeSource(HttpDataSource):
            def sync(self, start_date, end_date, code):
                return SyncDataResponse(
                    success=True,
                    data_source="fake",
                    code=code,
                    start_date=str(start_date),
                    end_date=str(end_date),
                    data=[{"code": "SJC", "price": 72.5}],
                    timestamp="2024-01-01",
                )
            def _format_request_date(self, d, is_end_date=False): return ""
            def _get_headers(self): return {}
            def _get_cookies(self): return {}

        source = FakeSource("http://fake", "fake")
        storage = DuckDBStorage(str(tmp_path / "pipeline.duckdb"))
        table = Table(
            name="gold",
            columns=[
                Column(name="code", data_type=DataType.STRING),
                Column(name="price", data_type=DataType.FLOAT),
            ],
        )

        pipeline = SyncPipeline(source, storage)
        result = pipeline.run(table, "SJC", date(2024, 1, 1), date(2024, 1, 31))

        assert result.success is True
        assert result.rows_fetched == 1
        assert result.rows_stored == 1
        assert result.data_source == "fake"
        storage.close()

    def test_pipeline_source_failure(self, tmp_path):
        from kactus_data.pipeline import SyncPipeline
        from kactus_data.storage.duckdb import DuckDBStorage
        from kactus_data.sources.http import HttpDataSource
        from kactus_common.database.duckdb.schema import Table, Column
        from kactus_common.database.duckdb.consts import DataType

        class FailSource(HttpDataSource):
            def sync(self, start_date, end_date, code):
                return SyncDataResponse(
                    success=False,
                    data_source="fail",
                    code=code,
                    start_date=str(start_date),
                    end_date=str(end_date),
                    error="Network error",
                    timestamp="2024-01-01",
                )
            def _format_request_date(self, d, is_end_date=False): return ""
            def _get_headers(self): return {}
            def _get_cookies(self): return {}

        source = FailSource("http://fail", "fail")
        storage = DuckDBStorage(str(tmp_path / "fail.duckdb"))
        table = Table(name="t", columns=[Column(name="x", data_type=DataType.STRING)])

        result = SyncPipeline(source, storage).run(table, "X", date(2024, 1, 1), date(2024, 1, 1))
        assert result.success is False
        assert result.error == "Network error"
        storage.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
