#!/usr/bin/env python3
"""Tests for the SyncPipeline — core pipeline and vnstock integration."""

import sys
import pytest
from datetime import date, datetime
from unittest.mock import MagicMock

import pandas as pd

from kactus_common.database.duckdb.consts import DataType
from kactus_common.database.duckdb.schema import Column, Table
from kactus_data.schemas import SyncDataResponse, SyncResult
from kactus_data.storage.duckdb import DuckDBStorage


def _create_vnstock_mock():
    mock_vnstock = MagicMock()
    sys.modules["vnstock"] = mock_vnstock
    return mock_vnstock


@pytest.fixture(autouse=True)
def vnstock_mock():
    yield
    sys.modules.pop("vnstock", None)


class TestSyncPipeline:
    """Tests for SyncPipeline with HttpDataSource."""

    def test_pipeline_success(self, tmp_path):
        from kactus_data.pipeline import SyncPipeline
        from kactus_data.sources.http import HttpDataSource

        class FakeSource(HttpDataSource):
            def sync(self, start_date, end_date, code):
                return SyncDataResponse(
                    success=True, data_source="fake", code=code,
                    start_date=str(start_date), end_date=str(end_date),
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
        result = SyncPipeline(source, storage).run(table, "SJC", date(2024, 1, 1), date(2024, 1, 31))
        assert result.success is True
        assert result.rows_fetched == 1
        storage.close()

    def test_pipeline_source_failure(self, tmp_path):
        from kactus_data.pipeline import SyncPipeline
        from kactus_data.sources.http import HttpDataSource

        class FailSource(HttpDataSource):
            def sync(self, start_date, end_date, code):
                return SyncDataResponse(
                    success=False, data_source="fail", code=code,
                    start_date=str(start_date), end_date=str(end_date),
                    error="Network error", timestamp="2024-01-01",
                )
            def _format_request_date(self, d, is_end_date=False): return ""
            def _get_headers(self): return {}
            def _get_cookies(self): return {}

        source = FailSource("http://fail", "fail")
        storage = DuckDBStorage(str(tmp_path / "fail.duckdb"))
        table = Table(name="t", columns=[Column(name="x", data_type=DataType.STRING)])
        result = SyncPipeline(source, storage).run(table, "X", date(2024, 1, 1), date(2024, 1, 1))
        assert result.success is False
        storage.close()


class TestVnstockPipeline:
    """Test SyncPipeline works with VnstockSource."""

    def test_ohlcv_pipeline(self, tmp_path):
        from kactus_data.pipeline import SyncPipeline
        from kactus_data.sources.stock.vnstock import VnstockOHLCVSource
        from kactus_data.sources.stock.tables import STOCK_OHLCV_TABLE

        mock_vnstock = _create_vnstock_mock()
        mock_df = pd.DataFrame({
            "time": [datetime(2024, 1, 2)],
            "open": [30.0], "high": [32.0], "low": [29.0],
            "close": [31.5], "volume": [1000000],
        })
        mock_quote = MagicMock()
        mock_quote.history.return_value = mock_df
        mock_vnstock.Quote.return_value = mock_quote

        source = VnstockOHLCVSource(source="KBS", interval="1D")
        storage = DuckDBStorage(str(tmp_path / "ohlcv.duckdb"))
        result = SyncPipeline(source, storage).run(
            table=STOCK_OHLCV_TABLE, code="VCI",
            start_date=date(2024, 1, 1), end_date=date(2024, 1, 31),
        )
        assert result.success is True
        assert result.rows_stored == 1

        df = storage.query("SELECT * FROM stock_ohlcv")
        assert df.iloc[0]["symbol"] == "VCI"
        storage.close()

    def test_listing_pipeline(self, tmp_path):
        from kactus_data.pipeline import SyncPipeline
        from kactus_data.sources.stock.vnstock import VnstockListingSource
        from kactus_data.sources.stock.tables import STOCK_LISTING_TABLE

        mock_vnstock = _create_vnstock_mock()
        mock_df = pd.DataFrame({
            "symbol": ["VCI", "ACB"],
            "organ_name": ["Vietcap", "ACB"],
        })
        mock_listing = MagicMock()
        mock_listing.all_symbols.return_value = mock_df
        mock_vnstock.Listing.return_value = mock_listing

        source = VnstockListingSource(source="KBS")
        storage = DuckDBStorage(str(tmp_path / "listing.duckdb"))
        result = SyncPipeline(source, storage).run(
            table=STOCK_LISTING_TABLE, code="ALL",
            start_date=date(2024, 1, 1), end_date=date(2024, 1, 1),
        )
        assert result.success is True
        assert result.rows_stored == 2
        storage.close()
