"""Portfolio request/response schemas."""

from __future__ import annotations

import datetime

from kactus_common.schemas import BaseSchema, FancyInt, OpaqueDict

from .const import AssetType, CrawlKind, CrawlTrigger


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


# --------------------------------------------------------------------------- #
# Crawl control + generic market rows — shared by both planes.
#
# The data plane returns these from ``/internal/*``; the control plane re-serves
# them on ``/api/*``. Defined once so the wire shape has a single owner.
# --------------------------------------------------------------------------- #
class MarketRowSchema(BaseSchema):
    """Generic decision-support row (foreign trade / ratios / events).

    Curated identity in ``symbol``; the full source row in ``data`` (opaque,
    shape varies by dataset and vnstock source)."""

    symbol: str | None = None
    data: OpaqueDict = {}


class CrawlJobSchema(BaseSchema):
    """A scheduled crawl job and its next fire time."""

    id: str
    next_run_time: str | None = None


class CrawlStatusSchema(BaseSchema):
    """Crawl/scheduler status snapshot (admin view, served by the data plane)."""

    scheduler_running: bool
    vnstock_tier: str | None = None
    jobs: list[CrawlJobSchema] = []


class CrawlTriggerResponse(BaseSchema):
    """Result of a manual crawl trigger."""

    crawl_run_ids: list[FancyInt] = []
    skipped: bool = False
    message: str = "ok"


class CrawlRequest(BaseSchema):
    """Body of ``POST /internal/crawl``.

    ``codes_by_type=None`` means "crawl the live watchlist union" — the data
    plane computes it from Postgres itself, so the control plane never has to
    ship the whole universe of symbols across the wire just to ask for a refresh.
    """

    kind: CrawlKind = CrawlKind.QUOTES
    codes_by_type: dict[str, list[str]] | None = None
    trigger: CrawlTrigger = CrawlTrigger.MANUAL
    portfolio_id: FancyInt | None = None
    #: Skip if a crawl of the same (asset_type, kind) is already in flight.
    dedup: bool = True
