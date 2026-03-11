"""Company data schemas."""

from __future__ import annotations

from pydantic import BaseModel


class CompanyItem(BaseModel):
    """Summary row for company list."""

    symbol: str
    company_name: str | None = None
    short_name: str | None = None
    industry: str | None = None
    exchange: str | None = None
    market_cap: float | None = None
    outstanding_shares: float | None = None
    source: str | None = None
    synced_at: str | None = None


class CompanyDetail(CompanyItem):
    """Full company detail including parsed overview JSON."""

    overview: dict | None = None


class CompanySyncRequest(BaseModel):
    """Request body for company sync."""

    symbol: str
