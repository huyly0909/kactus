"""Finance data schemas."""

from __future__ import annotations

from pydantic import BaseModel


class FinanceItem(BaseModel):
    """Summary row for finance list."""

    symbol: str
    period: str
    year: int
    quarter: int
    report_type: str
    source: str | None = None
    synced_at: str | None = None


class FinanceDetail(FinanceItem):
    """Full finance detail including parsed data JSON."""

    data: dict | None = None


class FinanceSyncRequest(BaseModel):
    """Request body for finance sync."""

    symbol: str
    report_type: str = "BalanceSheet"
    period: str = "quarter"
