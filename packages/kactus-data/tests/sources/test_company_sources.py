#!/usr/bin/env python3
"""Tests for company domain — VnstockCompanySource and table schemas."""

import json
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


class TestVnstockCompanySource:
    """Test Company source with mocked vnstock library."""

    def test_sync_success(self):
        from kactus_data.sources.company.vnstock import VnstockCompanySource

        mock_vnstock = _create_vnstock_mock()
        overview_df = pd.DataFrame([{
            "company_name": "Vietcap Securities",
            "short_name": "VCI",
            "industry": "Financial Services",
            "exchange": "HOSE",
            "market_cap": 5000000000,
            "outstanding_share": 200000000,
        }])

        mock_company = MagicMock()
        mock_company.overview.return_value = overview_df
        mock_stock = MagicMock()
        mock_stock.company = mock_company
        mock_root = MagicMock()
        mock_root.stock.return_value = mock_stock
        mock_vnstock.Vnstock.return_value = mock_root

        source = VnstockCompanySource(source="VCI")
        result = source.sync(date(2024, 1, 1), date(2024, 1, 1), "VCI")

        assert result.success is True
        assert len(result.data) == 1
        assert result.data[0]["symbol"] == "VCI"
        assert result.data[0]["company_name"] == "Vietcap Securities"

        parsed = json.loads(result.data[0]["overview_json"])
        assert parsed["company_name"] == "Vietcap Securities"


class TestCompanyTableSchema:
    """Test company table definition."""

    def test_primary_keys(self):
        from kactus_data.sources.company.tables import COMPANY_TABLE
        assert COMPANY_TABLE.get_primary_key_columns() == ["symbol"]

    def test_upsert_strategy(self):
        from kactus_common.database.duckdb.consts import UpdateStrategy
        from kactus_data.sources.company.tables import COMPANY_TABLE
        assert COMPANY_TABLE.update_strategy == UpdateStrategy.UPSERT
