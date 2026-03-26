"""Tests for FinanceService — DuckDB query logic.

Mocks DuckDBStorage to avoid needing an actual DuckDB instance.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
from kactus_fin.finance.service import FinanceService


def _make_storage(df: pd.DataFrame | None = None) -> MagicMock:
    storage = MagicMock()
    storage.query.return_value = df if df is not None else pd.DataFrame()
    return storage


def _sample_finance_row(**overrides) -> dict:
    base = {
        "symbol": "VNM",
        "period": "Q",
        "year": 2025,
        "quarter": 4,
        "report_type": "BalanceSheet",
        "source": "vnstock",
        "synced_at": "2026-01-01",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# list_finance
# ---------------------------------------------------------------------------


def test_list_finance_no_filters():
    df = pd.DataFrame([_sample_finance_row()])
    storage = _make_storage(df)
    result = FinanceService.list_finance(storage)
    assert len(result) == 1
    assert result[0].symbol == "VNM"
    # Verify SQL has no WHERE clause
    sql = storage.query.call_args[0][0]
    assert "WHERE" not in sql


def test_list_finance_with_symbol_filter():
    df = pd.DataFrame([_sample_finance_row()])
    storage = _make_storage(df)
    FinanceService.list_finance(storage, symbol="vnm")
    sql = storage.query.call_args[0][0]
    params = storage.query.call_args[0][1]
    assert "symbol = ?" in sql
    assert "VNM" in params  # symbol.upper()


def test_list_finance_with_report_type_filter():
    df = pd.DataFrame([_sample_finance_row()])
    storage = _make_storage(df)
    FinanceService.list_finance(storage, report_type="IncomeStatement")
    sql = storage.query.call_args[0][0]
    params = storage.query.call_args[0][1]
    assert "report_type = ?" in sql
    assert "IncomeStatement" in params


def test_list_finance_with_both_filters():
    df = pd.DataFrame([_sample_finance_row()])
    storage = _make_storage(df)
    FinanceService.list_finance(storage, symbol="vnm", report_type="BalanceSheet")
    sql = storage.query.call_args[0][0]
    params = storage.query.call_args[0][1]
    assert "?" in sql
    assert "AND" in sql
    assert "VNM" in params
    assert "BalanceSheet" in params


# ---------------------------------------------------------------------------
# get_finance
# ---------------------------------------------------------------------------


def test_get_finance_found():
    df = pd.DataFrame(
        [
            {
                **_sample_finance_row(),
                "data_json": '{"revenue": 1000000}',
            }
        ]
    )
    storage = _make_storage(df)
    result = FinanceService.get_finance(storage, "VNM")
    assert len(result) == 1
    assert result[0].data == {"revenue": 1000000}


def test_get_finance_not_found():
    storage = _make_storage(pd.DataFrame())
    result = FinanceService.get_finance(storage, "UNKNOWN")
    assert result == []


def test_get_finance_invalid_json():
    df = pd.DataFrame(
        [
            {
                **_sample_finance_row(),
                "data_json": "not valid json",
            }
        ]
    )
    storage = _make_storage(df)
    result = FinanceService.get_finance(storage, "VNM")
    assert len(result) == 1
    assert result[0].data is None


def test_get_finance_null_data():
    df = pd.DataFrame(
        [
            {
                **_sample_finance_row(),
                "data_json": None,
            }
        ]
    )
    storage = _make_storage(df)
    result = FinanceService.get_finance(storage, "VNM")
    assert len(result) == 1
    assert result[0].data is None
