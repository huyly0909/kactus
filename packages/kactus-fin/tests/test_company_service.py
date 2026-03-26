"""Tests for CompanyService — DuckDB query logic.

Mocks DuckDBStorage to avoid needing an actual DuckDB instance.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest
from kactus_fin.company.service import CompanyService


def _make_storage(df: pd.DataFrame | None = None) -> MagicMock:
    """Create a mock DuckDBStorage that returns the given DataFrame."""
    storage = MagicMock()
    storage.query.return_value = df if df is not None else pd.DataFrame()
    return storage


# ---------------------------------------------------------------------------
# list_companies
# ---------------------------------------------------------------------------


def test_list_companies():
    df = pd.DataFrame(
        [
            {
                "symbol": "VNM",
                "company_name": "Vinamilk",
                "short_name": "VNM",
                "industry": "Food",
                "exchange": "HOSE",
                "market_cap": 1000000,
                "outstanding_shares": 500000,
                "source": "vnstock",
                "synced_at": "2026-01-01",
            }
        ]
    )
    storage = _make_storage(df)
    result = CompanyService.list_companies(storage)
    assert len(result) == 1
    assert result[0].symbol == "VNM"
    assert result[0].company_name == "Vinamilk"


def test_list_companies_empty():
    storage = _make_storage(pd.DataFrame())
    result = CompanyService.list_companies(storage)
    assert result == []


# ---------------------------------------------------------------------------
# get_company
# ---------------------------------------------------------------------------


def test_get_company_found():
    df = pd.DataFrame(
        [
            {
                "symbol": "VNM",
                "company_name": "Vinamilk",
                "short_name": "VNM",
                "industry": "Food",
                "exchange": "HOSE",
                "market_cap": 1000000,
                "outstanding_shares": 500000,
                "source": "vnstock",
                "synced_at": "2026-01-01",
                "overview_json": '{"founded": 1976}',
            }
        ]
    )
    storage = _make_storage(df)
    result = CompanyService.get_company(storage, "VNM")
    assert result is not None
    assert result.symbol == "VNM"
    assert result.overview == {"founded": 1976}


def test_get_company_not_found():
    storage = _make_storage(pd.DataFrame())
    result = CompanyService.get_company(storage, "UNKNOWN")
    assert result is None


def test_get_company_invalid_json_overview():
    df = pd.DataFrame(
        [
            {
                "symbol": "VNM",
                "company_name": "Vinamilk",
                "short_name": "VNM",
                "industry": "Food",
                "exchange": "HOSE",
                "market_cap": 1000000,
                "outstanding_shares": 500000,
                "source": "vnstock",
                "synced_at": "2026-01-01",
                "overview_json": "not valid json {{{",
            }
        ]
    )
    storage = _make_storage(df)
    result = CompanyService.get_company(storage, "VNM")
    assert result is not None
    assert result.overview is None


def test_get_company_no_overview():
    df = pd.DataFrame(
        [
            {
                "symbol": "VNM",
                "company_name": "Vinamilk",
                "short_name": "VNM",
                "industry": "Food",
                "exchange": "HOSE",
                "market_cap": 1000000,
                "outstanding_shares": 500000,
                "source": "vnstock",
                "synced_at": "2026-01-01",
                "overview_json": None,
            }
        ]
    )
    storage = _make_storage(df)
    result = CompanyService.get_company(storage, "VNM")
    assert result is not None
    assert result.overview is None


# ---------------------------------------------------------------------------
# SQL injection documentation (current vulnerability)
# ---------------------------------------------------------------------------


def test_sql_injection_is_prevented():
    """Verify that user input is passed as parameters, not interpolated into SQL."""
    storage = _make_storage(pd.DataFrame())
    malicious = "'; DROP TABLE stock_company; --"
    CompanyService.get_company(storage, malicious)

    called_sql = storage.query.call_args[0][0]
    called_params = storage.query.call_args[0][1]
    # SQL should use ? placeholder, not contain the raw input
    assert malicious not in called_sql, "Raw user input should NOT be in SQL"
    assert "?" in called_sql, "SQL should use parameterized placeholder"
    assert called_params == [malicious], "Malicious input should be in params list"
