"""Portfolio admin API — superuser-only oversight & manual ops.

Manual crawl triggers *enqueue* into the shared sync queue (plain Postgres
insert — same pattern as the gold admin API); the data-plane dispatcher
executes them.  The request runs inside the user context, so ``created_by``
auto-populates on the queued job.  Anything about the *crawler itself* — its
scheduler, its vnstock tier — is forwarded to the data plane, because that is
where the scheduler lives and it is the only process that knows.

Crawl history lives in the queue (``GET /api/market/sync/jobs/search``); the
old ``CrawlRun`` table is retired.
"""

from __future__ import annotations

from fastapi import Request
from kactus_common.portfolio.const import CrawlKind, CrawlTrigger
from kactus_common.portfolio.crawl_queue import enqueue_catalog_sync, enqueue_crawl_jobs
from kactus_common.portfolio.schema import (
    CrawlStatusSchema,
    CrawlTriggerResponse,
    PortfolioSchema,
)
from kactus_common.portfolio.service import PortfolioService
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


@router.get("/crawl-status")
async def crawl_status(request: Request) -> CrawlStatusSchema:
    """Scheduler + vnstock tier status, read from the data plane (admin)."""
    return await data_client.scheduler_status()


@router.post("/crawl/run-now")
@provide_session
async def crawl_run_now(
    request: Request,
    session: AsyncSession,
    kind: CrawlKind = CrawlKind.QUOTES,
) -> CrawlTriggerResponse:
    """Enqueue an immediate crawl of the live watchlist union (admin).

    No codes shipped: the handler resolves the union from the same Postgres at
    run time.  ``skipped`` means the identical job is already queued/running.
    """
    created, existing = await enqueue_crawl_jobs(
        session, kind=kind, trigger=CrawlTrigger.MANUAL
    )
    if not created:
        message = (
            f"Crawl '{kind}' already queued/running"
            if existing
            else f"No asset type produces '{kind}'"
        )
        return CrawlTriggerResponse(skipped=True, message=message)
    return CrawlTriggerResponse(
        job_ids=[j.id for j in created],
        skipped=False,
        message=f"Crawl '{kind}' queued",
    )


@router.post("/catalog/sync")
@provide_session
async def catalog_sync(request: Request, session: AsyncSession) -> CrawlTriggerResponse:
    """Enqueue the supported-asset catalog refresh (admin)."""
    job, created = await enqueue_catalog_sync(session, trigger=CrawlTrigger.MANUAL)
    if not created:
        return CrawlTriggerResponse(
            skipped=True, message="Catalog sync already queued/running"
        )
    return CrawlTriggerResponse(
        job_ids=[job.id], skipped=False, message="Catalog sync queued"
    )
