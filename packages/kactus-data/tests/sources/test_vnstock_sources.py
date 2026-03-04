#!/usr/bin/env python3
"""Tests for stock domain — VnstockSource ABC, OHLCV, and listing sources."""

import sys
import pytest
from datetime import date, datetime
from unittest.mock import MagicMock

import pandas as pd

from kactus_data.schemas import SyncDataResponse


def _create_vnstock_mock():
    mock_vnstock = MagicMock()
    sys.modules["vnstock"] = mock_vnstock
    return mock_vnstock


@pytest.fixture(autouse=True)
def vnstock_mock():
    yield
    sys.modules.pop("vnstock", None)


class TestVnstockSourceABC:
    """Test the VnstockSource abstract base class."""

    def test_cannot_instantiate_abstract(self):
        from kactus_data.sources.stock.base import VnstockSource
        with pytest.raises(TypeError):
            VnstockSource("test", "KBS")

    def test_concrete_implementation(self):
        from kactus_data.sources.stock.base import VnstockSource

        class FakeSource(VnstockSource):
            def sync(self, start_date, end_date, code):
                return SyncDataResponse(
                    success=True, data_source=self.name, code=code,
                    start_date=str(start_date), end_date=str(end_date),
                    data=[], timestamp=datetime.now().isoformat(),
                )

        source = FakeSource(name="fake", source="KBS")
        assert source.name == "fake"
        assert source.source == "KBS"
        result = source.sync(date(2024, 1, 1), date(2024, 1, 31), "VCI")
        assert result.success is True


class TestVnstockOHLCVSource:
    """Test OHLCV source with mocked vnstock library."""

    def test_init_defaults(self):
        from kactus_data.sources.stock.vnstock import VnstockOHLCVSource
        source = VnstockOHLCVSource()
        assert source.name == "vnstock_ohlcv"
        assert source.source == "KBS"
        assert source.interval == "1D"

    def test_sync_success(self):
        from kactus_data.sources.stock.vnstock import VnstockOHLCVSource
        mock_vnstock = _create_vnstock_mock()
        mock_df = pd.DataFrame({
            "time": [datetime(2024, 1, 2), datetime(2024, 1, 3)],
            "open": [30.0, 31.0], "high": [32.0, 33.0],
            "low": [29.0, 30.0], "close": [31.5, 32.5],
            "volume": [1000000, 1200000],
        })
        mock_quote = MagicMock()
        mock_quote.history.return_value = mock_df
        mock_vnstock.Quote.return_value = mock_quote

        result = VnstockOHLCVSource(source="KBS", interval="1D").sync(date(2024, 1, 1), date(2024, 1, 31), "VCI")
        assert result.success is True
        assert len(result.data) == 2
        assert result.data[0]["symbol"] == "VCI"

    def test_sync_empty(self):
        from kactus_data.sources.stock.vnstock import VnstockOHLCVSource
        mock_vnstock = _create_vnstock_mock()
        mock_quote = MagicMock()
        mock_quote.history.return_value = pd.DataFrame()
        mock_vnstock.Quote.return_value = mock_quote
        result = VnstockOHLCVSource().sync(date(2024, 1, 1), date(2024, 1, 31), "XYZ")
        assert result.success is True
        assert result.data == []

    def test_sync_error(self):
        from kactus_data.sources.stock.vnstock import VnstockOHLCVSource
        mock_vnstock = _create_vnstock_mock()
        mock_vnstock.Quote.side_effect = Exception("API rate limit exceeded")
        result = VnstockOHLCVSource().sync(date(2024, 1, 1), date(2024, 1, 31), "VCI")
        assert result.success is False


class TestVnstockListingSource:
    """Test Listing source with mocked vnstock library."""

    def test_sync_success(self):
        from kactus_data.sources.stock.vnstock import VnstockListingSource
        mock_vnstock = _create_vnstock_mock()
        mock_df = pd.DataFrame({
            "symbol": ["VCI", "ACB", "VCB"],
            "organ_name": ["Vietcap", "ACB", "VCB"],
        })
        mock_listing = MagicMock()
        mock_listing.all_symbols.return_value = mock_df
        mock_vnstock.Listing.return_value = mock_listing

        result = VnstockListingSource(source="KBS").sync(date(2024, 1, 1), date(2024, 1, 1), "ALL")
        assert result.success is True
        assert len(result.data) == 3


class TestStockTableSchemas:
    """Test stock table definitions."""

    def test_ohlcv_primary_keys(self):
        from kactus_data.sources.stock.tables import STOCK_OHLCV_TABLE
        pks = STOCK_OHLCV_TABLE.get_primary_key_columns()
        assert set(pks) == {"symbol", "time", "interval"}

    def test_listing_primary_keys(self):
        from kactus_data.sources.stock.tables import STOCK_LISTING_TABLE
        assert STOCK_LISTING_TABLE.get_primary_key_columns() == ["symbol"]
