"""Portfolio API — user-owned watchlists, market reads, manual refresh, SSE.

Portfolios are user-owned: every route resolves ownership via
``request.state.user`` (not project-scoped Casbin).  Market data comes from the
data plane over HTTP — this process cannot open DuckDB, which the crawler holds
read-write.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict

from fastapi import Request
from kactus_common.portfolio.const import AssetType, CrawlKind, CrawlTrigger
from kactus_common.portfolio.schema import (
    CrawlTriggerResponse,
    MarketRowSchema,
    PortfolioCreateRequest,
    PortfolioDetailSchema,
    PortfolioItemCreateRequest,
    PortfolioItemSchema,
    PortfolioSchema,
    PortfolioUpdateRequest,
    SupportedAssetSchema,
)
from kactus_common.portfolio.service import (
    CrawlRunService,
    PortfolioService,
    SupportedAssetService,
)
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import MessageResponse, Pagination
from kactus_common.sse.broker import get_sse_broker
from kactus_fin import data_client
from kactus_fin.dependencies import provide_session
from kactus_fin.portfolio.schema import MarketNewsSchema, MarketQuoteSchema
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

router = KactusAPIRouter(prefix="/api/portfolios", tags=["portfolios"])
assets_router = KactusAPIRouter(prefix="/api/assets", tags=["assets"])

_HEARTBEAT_SECONDS = 15


# --------------------------------------------------------------------------- #
# SSE — declared before parametric routes so "/stream" never matches "/{id}".
# --------------------------------------------------------------------------- #
@router.get("/stream", response_class=EventSourceResponse)
async def stream_market_events(request: Request):
    """Live market-refresh stream (all subscribers get every nudge).

    Bypasses ``ResponseModel`` wrapping via ``response_class``. Emits a
    heartbeat every ~15s so proxies keep the connection open.
    """
    broker = get_sse_broker()
    queue = await broker.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(
                        queue.get(), timeout=_HEARTBEAT_SECONDS
                    )
                    yield {"event": "data_refreshed", "data": json.dumps(message)}
                except asyncio.TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
        finally:
            broker.unsubscribe(queue)

    return EventSourceResponse(event_generator())


# --------------------------------------------------------------------------- #
# Portfolio CRUD
# --------------------------------------------------------------------------- #
@router.post("")
@provide_session
async def create_portfolio(
    body: PortfolioCreateRequest,
    request: Request,
    session: AsyncSession,
) -> PortfolioSchema:
    """Create a portfolio owned by the current user."""
    user = request.state.user
    portfolio = await PortfolioService.create(
        session, name=body.name, description=body.description, owner_id=user.id
    )
    return PortfolioSchema.model_validate(portfolio)


@router.get("")
@provide_session
async def list_portfolios(
    request: Request, session: AsyncSession
) -> Pagination[PortfolioSchema]:
    """List the current user's portfolios."""
    user = request.state.user
    portfolios = await PortfolioService.list_for_owner(session, user.id)
    items = [PortfolioSchema.model_validate(p) for p in portfolios]
    return Pagination(total=len(items), items=items)


@router.get("/{portfolio_id}")
@provide_session
async def get_portfolio(
    portfolio_id: int, request: Request, session: AsyncSession
) -> PortfolioDetailSchema:
    """Get a portfolio with its watchlist items."""
    user = request.state.user
    portfolio = await PortfolioService.get_owned_or_404(
        session, portfolio_id=portfolio_id, owner_id=user.id
    )
    items = await PortfolioService.get_items(session, portfolio_id)
    detail = PortfolioDetailSchema.model_validate(portfolio)
    detail.items = [PortfolioItemSchema.model_validate(i) for i in items]
    return detail


@router.put("/{portfolio_id}")
@provide_session
async def update_portfolio(
    portfolio_id: int,
    body: PortfolioUpdateRequest,
    request: Request,
    session: AsyncSession,
) -> PortfolioSchema:
    """Update a portfolio's name/description."""
    user = request.state.user
    portfolio = await PortfolioService.get_owned_or_404(
        session, portfolio_id=portfolio_id, owner_id=user.id
    )
    portfolio = await PortfolioService.update(
        session, portfolio, name=body.name, description=body.description
    )
    return PortfolioSchema.model_validate(portfolio)


@router.delete("/{portfolio_id}")
@provide_session
async def delete_portfolio(
    portfolio_id: int, request: Request, session: AsyncSession
) -> MessageResponse:
    """Logically delete a portfolio."""
    user = request.state.user
    portfolio = await PortfolioService.get_owned_or_404(
        session, portfolio_id=portfolio_id, owner_id=user.id
    )
    await PortfolioService.delete(session, portfolio)
    return MessageResponse(message="deleted")


# --------------------------------------------------------------------------- #
# Watchlist items
# --------------------------------------------------------------------------- #
@router.post("/{portfolio_id}/items")
@provide_session
async def add_item(
    portfolio_id: int,
    body: PortfolioItemCreateRequest,
    request: Request,
    session: AsyncSession,
) -> PortfolioItemSchema:
    """Add an instrument to a portfolio (validated against the catalog)."""
    user = request.state.user
    await PortfolioService.get_owned_or_404(
        session, portfolio_id=portfolio_id, owner_id=user.id
    )
    item = await PortfolioService.add_item(
        session, portfolio_id=portfolio_id, asset_type=body.asset_type, code=body.code
    )
    return PortfolioItemSchema.model_validate(item)


@router.delete("/{portfolio_id}/items")
@provide_session
async def remove_item(
    portfolio_id: int,
    code: str,
    request: Request,
    session: AsyncSession,
    asset_type: AssetType = AssetType.STOCK,
) -> MessageResponse:
    """Remove an instrument from a portfolio."""
    user = request.state.user
    await PortfolioService.get_owned_or_404(
        session, portfolio_id=portfolio_id, owner_id=user.id
    )
    await PortfolioService.remove_item(
        session, portfolio_id=portfolio_id, asset_type=asset_type, code=code
    )
    return MessageResponse(message="removed")


# --------------------------------------------------------------------------- #
# Market reads (from the data plane over HTTP)
# --------------------------------------------------------------------------- #
async def _items_by_type(
    session: AsyncSession, portfolio_id: int
) -> dict[AssetType, list[str]]:
    items = await PortfolioService.get_items(session, portfolio_id)
    grouped: dict[AssetType, list[str]] = defaultdict(list)
    for it in items:
        grouped[AssetType(it.asset_type)].append(it.code)
    return grouped


@router.get("/{portfolio_id}/quotes")
@provide_session
async def get_quotes(
    portfolio_id: int, request: Request, session: AsyncSession
) -> list[MarketQuoteSchema]:
    """Latest quotes for every instrument in the portfolio."""
    user = request.state.user
    await PortfolioService.get_owned_or_404(
        session, portfolio_id=portfolio_id, owner_id=user.id
    )
    grouped = await _items_by_type(session, portfolio_id)
    out: list[MarketQuoteSchema] = []
    for asset_type, codes in grouped.items():
        rows = await data_client.read_assets(asset_type, CrawlKind.QUOTES, codes)
        for row in rows:
            r = row.data
            out.append(
                MarketQuoteSchema(
                    asset_type=asset_type,
                    code=row.symbol,
                    match_price=r.get("match_price"),
                    ref_price=r.get("ref_price"),
                    ceiling=r.get("ceiling"),
                    floor=r.get("floor"),
                    buy_price=r.get("buy_price"),
                    sell_price=r.get("sell_price"),
                    unit=r.get("unit"),
                    volume=r.get("accumulated_volume"),
                    source=r.get("source"),
                    crawled_at=r.get("crawled_at"),
                )
            )
    return out


@router.get("/{portfolio_id}/news")
@provide_session
async def get_news(
    portfolio_id: int, request: Request, session: AsyncSession
) -> list[MarketNewsSchema]:
    """Recent news for the portfolio's stock instruments."""
    user = request.state.user
    await PortfolioService.get_owned_or_404(
        session, portfolio_id=portfolio_id, owner_id=user.id
    )
    grouped = await _items_by_type(session, portfolio_id)
    out: list[MarketNewsSchema] = []
    for asset_type, codes in grouped.items():
        rows = await data_client.read_assets(asset_type, CrawlKind.NEWS, codes)
        out.extend(MarketNewsSchema.model_validate(row.data) for row in rows)
    return out


@router.post("/{portfolio_id}/refresh")
@provide_session
async def refresh_portfolio(
    portfolio_id: int,
    request: Request,
    session: AsyncSession,
    kind: CrawlKind = CrawlKind.QUOTES,
) -> CrawlTriggerResponse:
    """Manually trigger a crawl for this portfolio (deduped vs in-flight runs)."""
    user = request.state.user
    await PortfolioService.get_owned_or_404(
        session, portfolio_id=portfolio_id, owner_id=user.id
    )
    grouped = await _items_by_type(session, portfolio_id)
    if not grouped:
        return CrawlTriggerResponse(skipped=True, message="Portfolio is empty")

    for asset_type in grouped:
        if await CrawlRunService.has_inflight(
            session, asset_type=asset_type, kind=kind
        ):
            return CrawlTriggerResponse(
                skipped=True, message="A refresh is already in progress"
            )

    # Awaited, not fired into a local BackgroundTasks: the data plane already
    # returns as soon as it has queued the crawl, and awaiting means a data
    # plane that is down surfaces as an error to the user instead of a
    # "Refresh scheduled" that quietly never happened.
    await data_client.trigger_crawl(
        kind=kind,
        codes_by_type={str(at): codes for at, codes in grouped.items()},
        trigger=CrawlTrigger.MANUAL,
        portfolio_id=portfolio_id,
        dedup=True,
    )
    return CrawlTriggerResponse(skipped=False, message="Refresh scheduled")


# --------------------------------------------------------------------------- #
# Asset catalog + decision-support detail reads
# --------------------------------------------------------------------------- #
@assets_router.get("/supported")
@provide_session
async def search_supported_assets(
    request: Request,
    session: AsyncSession,
    asset_type: AssetType | None = None,
    q: str | None = None,
    tag: str | None = None,
    limit: int = 50,
) -> Pagination[SupportedAssetSchema]:
    """Search the crawlable instrument catalog (asset picker)."""
    assets = await SupportedAssetService.search(
        session, asset_type=asset_type, q=q, tag=tag, limit=limit
    )
    items = [SupportedAssetSchema.model_validate(a) for a in assets]
    return Pagination(total=len(items), items=items)


@assets_router.get("/{asset_type}/{code}/{kind}")
async def get_asset_detail(
    asset_type: AssetType, code: str, kind: CrawlKind, request: Request
) -> list[MarketRowSchema]:
    """Decision-support detail (foreign trade / ratios / events) for one asset.

    A straight pass-through: the data plane already normalises the DuckDB cells
    into JSON-safe values, so there is nothing left to project here.
    """
    return await data_client.read_assets(asset_type, kind, [code.upper()])
