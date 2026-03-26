"""Tests for StockService — DuckDB query logic.

Mocks DuckDBStorage to avoid needing an actual DuckDB instance.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
from kactus_fin.stock.service import StockService


def _make_storage(df: pd.DataFrame | None = None) -> MagicMock:
    storage = MagicMock()
    storage.query.return_value = df if df is not None else pd.DataFrame()
    return storage


# ---------------------------------------------------------------------------
# list_stocks
# ---------------------------------------------------------------------------


def test_list_stocks():
    df = pd.DataFrame(
        [
            {"symbol": "VNM", "organ_name": "Vinamilk", "source": "vnstock", "synced_at": "2026-01-01"},
            {"symbol": "FPT", "organ_name": "FPT Corp", "source": "vnstock", "synced_at": "2026-01-01"},
        ]
    )
    storage = _make_storage(df)
    result = StockService.list_stocks(storage)
    assert len(result) == 2
    assert result[0].symbol == "VNM"


def test_list_stocks_empty():
    storage = _make_storage(pd.DataFrame())
    result = StockService.list_stocks(storage)
    assert result == []


# ---------------------------------------------------------------------------
# get_ohlcv
# ---------------------------------------------------------------------------


def test_get_ohlcv():
    df = pd.DataFrame(
        [
            {
                "symbol": "VNM",
                "time": "2026-01-01",
                "interval": "1D",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 103.0,
                "volume": 50000,
                "source": "vnstock",
            }
        ]
    )
    storage = _make_storage(df)
    result = StockService.get_ohlcv(storage, "VNM")
    assert len(result) == 1
    assert result[0].symbol == "VNM"
    assert result[0].close == 103.0


def test_get_ohlcv_empty():
    storage = _make_storage(pd.DataFrame())
    result = StockService.get_ohlcv(storage, "UNKNOWN")
    assert result == []
