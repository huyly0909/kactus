"""Stock data schemas."""

from __future__ import annotations

from pydantic import BaseModel


class StockListingItem(BaseModel):
    """Summary row for stock listing."""

    symbol: str
    organ_name: str | None = None
    source: str | None = None
    synced_at: str | None = None


class OhlcvItem(BaseModel):
    """Single OHLCV data point."""

    symbol: str
    time: str
    interval: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    source: str | None = None


class SyncOhlcvRequest(BaseModel):
    """Request body for OHLCV sync."""

    symbol: str
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    interval: str = "1D"
