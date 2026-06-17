"""Portfolio admin API — superuser-only oversight & manual ops."""

from __future__ import annotations

from fastapi import BackgroundTasks, Request
from kactus_common.portfolio.const import CrawlKind, CrawlTrigger
from kactus_common.portfolio.schema import CrawlRunSchema, PortfolioSchema
from kactus_common.portfolio.service import CrawlRunService, PortfolioService
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination
from kactus_data.jobs.crawl import run_crawl, sync_catalog
from kactus_data.sources.stock.auth import _safe_tier_name
from kactus_fin.dependencies import provide_session
from kactus_fin.portfolio.runtime import get_runtime
from kactus_fin.portfolio.schema import (
    CrawlJobSchema,
    CrawlStatusSchema,
    CrawlTriggerResponse,
)
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
    """Scheduler + vnstock tier status (admin)."""
    runtime = get_runtime()
    scheduler = runtime.scheduler
    jobs: list[CrawlJobSchema] = []
    running = False
    if scheduler is not None:
        running = scheduler.running
        for job in scheduler.get_jobs():
            nrt = getattr(job, "next_run_time", None)
            jobs.append(
                CrawlJobSchema(id=job.id, next_run_time=nrt.isoformat() if nrt else None)
            )
    return CrawlStatusSchema(
        scheduler_running=running, vnstock_tier=_safe_tier_name(), jobs=jobs
    )


@router.post("/crawl/run-now")
async def crawl_run_now(
    request: Request,
    background: BackgroundTasks,
    kind: CrawlKind = CrawlKind.QUOTES,
) -> CrawlTriggerResponse:
    """Trigger an immediate crawl of the live watchlist union (admin)."""
    runtime = get_runtime()
    background.add_task(
        run_crawl,
        db=runtime.db,
        providers=runtime.providers,
        kind=kind,
        symbol_provider=runtime.symbol_provider,
        trigger=CrawlTrigger.MANUAL,
        dedup=True,
    )
    return CrawlTriggerResponse(skipped=False, message=f"Crawl '{kind}' scheduled")


@router.post("/catalog/sync")
async def catalog_sync(request: Request, background: BackgroundTasks) -> CrawlTriggerResponse:
    """Refresh the supported-asset catalog for all providers (admin)."""
    runtime = get_runtime()
    background.add_task(sync_catalog, db=runtime.db, providers=runtime.providers)
    return CrawlTriggerResponse(skipped=False, message="Catalog sync scheduled")
