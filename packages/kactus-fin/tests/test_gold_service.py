"""Tests for GoldService — DuckDB query logic.

Mocks DuckDBStorage to avoid needing an actual DuckDB instance.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest
from kactus_common.exceptions import ConfigurationError
from kactus_fin.gold.service import GoldService


def _make_storage(df: pd.DataFrame | None = None) -> MagicMock:
    storage = MagicMock()
    storage.query.return_value = df if df is not None else pd.DataFrame()
    return storage


# ---------------------------------------------------------------------------
# list_gold_vn
# ---------------------------------------------------------------------------


def test_list_gold_vn():
    df = pd.DataFrame(
        [
            {"brand": "sjc", "type": "1L", "buy_price": 92.0, "sell_price": 94.0, "source": "vnappmob_gold", "synced_at": "2026-03-28"},
            {"brand": "sjc", "type": "5c", "buy_price": 91.5, "sell_price": 93.5, "source": "vnappmob_gold", "synced_at": "2026-03-28"},
        ]
    )
    storage = _make_storage(df)
    result = GoldService.list_gold_vn(storage)
    assert len(result) == 2
    assert result[0].brand == "sjc"
    assert result[0].buy_price == 92.0


def test_list_gold_vn_filtered_by_brand():
    df = pd.DataFrame(
        [{"brand": "doji", "type": "1L", "buy_price": 91.0, "sell_price": 93.0, "source": "vnappmob_gold", "synced_at": "2026-03-28"}]
    )
    storage = _make_storage(df)
    result = GoldService.list_gold_vn(storage, brand="doji")
    assert len(result) == 1
    # Verify parameterized query was used
    called_sql = storage.query.call_args[0][0]
    called_params = storage.query.call_args[0][1]
    assert "?" in called_sql
    assert called_params == ["doji"]


def test_list_gold_vn_empty():
    storage = _make_storage(pd.DataFrame())
    result = GoldService.list_gold_vn(storage)
    assert result == []


# ---------------------------------------------------------------------------
# list_gold_global
# ---------------------------------------------------------------------------


def test_list_gold_global():
    df = pd.DataFrame(
        [{"metal": "XAU", "currency": "USD", "price": 2350.50, "source": "metals_api", "synced_at": "2026-03-28"}]
    )
    storage = _make_storage(df)
    result = GoldService.list_gold_global(storage)
    assert len(result) == 1
    assert result[0].metal == "XAU"
    assert result[0].price == 2350.50


def test_list_gold_global_filtered_by_metal():
    df = pd.DataFrame(
        [{"metal": "XAG", "currency": "USD", "price": 28.50, "source": "metals_api", "synced_at": "2026-03-28"}]
    )
    storage = _make_storage(df)
    result = GoldService.list_gold_global(storage, metal="XAG")
    assert len(result) == 1
    called_sql = storage.query.call_args[0][0]
    called_params = storage.query.call_args[0][1]
    assert "?" in called_sql
    assert called_params == ["XAG"]


def test_list_gold_global_empty():
    storage = _make_storage(pd.DataFrame())
    result = GoldService.list_gold_global(storage)
    assert result == []


# ---------------------------------------------------------------------------
# sync — missing config
# ---------------------------------------------------------------------------


def test_sync_gold_vn_missing_token():
    storage = _make_storage()
    with pytest.raises(ConfigurationError):
        GoldService.sync_gold_vn(storage, brand="sjc", token=None)


def test_sync_gold_global_missing_api_key():
    storage = _make_storage()
    with pytest.raises(ConfigurationError):
        GoldService.sync_gold_global(storage, metal="XAU", api_key=None)


# ---------------------------------------------------------------------------
# SQL injection prevention
# ---------------------------------------------------------------------------


def test_gold_vn_sql_injection_prevented():
    storage = _make_storage(pd.DataFrame())
    malicious = "'; DROP TABLE gold_vn; --"
    GoldService.list_gold_vn(storage, brand=malicious)
    called_sql = storage.query.call_args[0][0]
    called_params = storage.query.call_args[0][1]
    assert malicious not in called_sql
    assert "?" in called_sql
    assert called_params == [malicious.lower()]


def test_gold_global_sql_injection_prevented():
    storage = _make_storage(pd.DataFrame())
    malicious = "'; DROP TABLE gold_global; --"
    GoldService.list_gold_global(storage, metal=malicious)
    called_sql = storage.query.call_args[0][0]
    called_params = storage.query.call_args[0][1]
    assert malicious not in called_sql
    assert "?" in called_sql
    assert called_params == [malicious.upper()]
