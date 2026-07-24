"""Portfolio admin API — superuser-only oversight & manual ops.

Reads of the audit trail (``CrawlRun``, portfolios) come from Postgres, which
both planes share. Anything about the *crawler itself* — its scheduler, its
vnstock tier, running one now — is forwarded to the data plane, because that is
where the scheduler lives and it is the only process that knows.
"""

from __future__ import annotations

from fastapi import Request
from kactus_common.portfolio.const import CrawlKind, CrawlTrigger
from kactus_common.portfolio.schema import (
    CrawlRunSchema,
    CrawlStatusSchema,
    CrawlTriggerResponse,
    PortfolioSchema,
)
from kactus_common.portfolio.service import CrawlRunService, PortfolioService
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination
from kactus_fin import data_client
from kactus_fin.dependencies import provide_session
from sqlalchemy.ext.asyncio import AsyncSession

router = KactusAPIRouter(prefix="/api/admin/portfolios", tags=["admin-portfolios"])


@router.get("")
@provide_session
async def list_all_portfolios(
    request: Request, session: AsyncSession
) -> Pagination[PortfolioSchema]:
    """List every user's portfolios (admin)."""
    portfolios = await PortfolioService.list_all(session)
    items = [PortfolioSchema.model_validate(p) for p in portfolios]
    return Pagination(total=len(items), items=items)


@router.get("/crawl-runs")
@provide_session
async def list_crawl_runs(
    request: Request, session: AsyncSession, limit: int = 50
) -> Pagination[CrawlRunSchema]:
    """Recent crawl-run audit records (admin)."""
    runs = await CrawlRunService.list_recent(session, limit=limit)
    items = [CrawlRunSchema.model_validate(r) for r in runs]
    return Pagination(total=len(items), items=items)


@router.get("/crawl-status")
async def crawl_status(request: Request) -> CrawlStatusSchema:
    """Scheduler + vnstock tier status, read from the data plane (admin)."""
    return await data_client.scheduler_status()


@router.post("/crawl/run-now")
async def crawl_run_now(
    request: Request,
    kind: CrawlKind = CrawlKind.QUOTES,
) -> CrawlTriggerResponse:
    """Trigger an immediate crawl of the live watchlist union (admin).

    No ``codes_by_type``: the data plane computes the union itself, from the
    same Postgres this process would have read it from.
    """
    return await data_client.trigger_crawl(kind=kind, trigger=CrawlTrigger.MANUAL)


@router.post("/catalog/sync")
async def catalog_sync(request: Request) -> CrawlTriggerResponse:
    """Refresh the supported-asset catalog for all providers (admin)."""
    return await data_client.sync_catalog()
