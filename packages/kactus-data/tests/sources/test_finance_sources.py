#!/usr/bin/env python3
"""Tests for finance domain — VnstockFinanceSource and table schemas."""

import json
import sys
import pytest
from datetime import date
from unittest.mock import MagicMock

import pandas as pd


def _create_vnstock_mock():
    mock_vnstock = MagicMock()
    sys.modules["vnstock"] = mock_vnstock
    return mock_vnstock


@pytest.fixture(autouse=True)
def vnstock_mock():
    yield
    sys.modules.pop("vnstock", None)


class TestVnstockFinanceSource:
    """Test Finance source with mocked vnstock library."""

    def test_invalid_report_type(self):
        from kactus_data.sources.finance.vnstock import VnstockFinanceSource
        with pytest.raises(ValueError, match="report_type must be one of"):
            VnstockFinanceSource(report_type="invalid_type")

    def test_valid_report_types(self):
        from kactus_data.sources.finance.vnstock import VnstockFinanceSource
        for report_type in ("income_statement", "balance_sheet", "cash_flow", "ratio"):
            source = VnstockFinanceSource(report_type=report_type)
            assert source.report_type == report_type

    def test_sync_success(self):
        from kactus_data.sources.finance.vnstock import VnstockFinanceSource

        mock_vnstock = _create_vnstock_mock()
        mock_df = pd.DataFrame([
            {"year": 2024, "quarter": 1, "revenue": 100000, "net_income": 20000},
            {"year": 2024, "quarter": 2, "revenue": 120000, "net_income": 25000},
        ])
        mock_finance = MagicMock()
        mock_finance.income_statement.return_value = mock_df
        mock_vnstock.Finance.return_value = mock_finance

        source = VnstockFinanceSource(report_type="income_statement", period="quarter")
        result = source.sync(date(2024, 1, 1), date(2024, 12, 31), "VCI")

        assert result.success is True
        assert len(result.data) == 2
        assert result.data[0]["symbol"] == "VCI"
        assert result.data[0]["report_type"] == "income_statement"

        parsed = json.loads(result.data[0]["data_json"])
        assert parsed["revenue"] == 100000


class TestFinanceTableSchema:
    """Test finance table definition."""

    def test_primary_keys(self):
        from kactus_data.sources.finance.tables import FINANCE_TABLE
        pks = FINANCE_TABLE.get_primary_key_columns()
        assert set(pks) == {"symbol", "period", "year", "quarter", "report_type"}

    def test_upsert_strategy(self):
        from kactus_common.database.duckdb.consts import UpdateStrategy
        from kactus_data.sources.finance.tables import FINANCE_TABLE
        assert FINANCE_TABLE.update_strategy == UpdateStrategy.UPSERT
