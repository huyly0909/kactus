"""Portfolio request/response schemas."""

from __future__ import annotations

import datetime

from kactus_common.schemas import BaseSchema, FancyInt

from .const import AssetType


class PortfolioSchema(BaseSchema):
    """Public portfolio information."""

    id: FancyInt
    name: str
    description: str | None = None
    owner_id: FancyInt


class PortfolioCreateRequest(BaseSchema):
    """Request body for creating a portfolio."""

    name: str
    description: str | None = None


class PortfolioUpdateRequest(BaseSchema):
    """Request body for updating a portfolio."""

    name: str | None = None
    description: str | None = None


class PortfolioItemSchema(BaseSchema):
    """A single watchlist membership."""

    id: FancyInt
    portfolio_id: FancyInt
    asset_type: AssetType
    code: str


class PortfolioItemCreateRequest(BaseSchema):
    """Request body for adding an instrument to a portfolio."""

    asset_type: AssetType = AssetType.STOCK
    code: str


class PortfolioDetailSchema(PortfolioSchema):
    """Portfolio with its watchlist items."""

    items: list[PortfolioItemSchema] = []


class SupportedAssetSchema(BaseSchema):
    """Catalog entry returned by the asset-picker."""

    id: FancyInt
    asset_type: AssetType
    code: str
    name: str | None = None
    is_crawlable: bool = True
    tags: list[str] = []
    meta_json: dict = {}


class CrawlRunSchema(BaseSchema):
    """Crawl execution audit record (admin / status views)."""

    id: FancyInt
    asset_type: AssetType
    kind: str
    trigger: str
    portfolio_id: FancyInt | None = None
    status: str
    rows_written: int
    error: str | None = None
    started_at: datetime.datetime | None = None
    finished_at: datetime.datetime | None = None
