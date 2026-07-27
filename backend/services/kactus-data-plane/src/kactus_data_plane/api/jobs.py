"""``/internal/crawl``, ``/internal/catalog/sync``, ``/internal/scheduler/status``.

Commands, not events — deliberately HTTP rather than a Redis queue. A crawl
trigger has a caller who wants to know whether it was accepted or deduped, and
a status code, a timeout and a stack trace are the cheapest way to tell them.
Redis carries the *result* (the SSE nudge, fire-and-forget); the ask travels
over HTTP.

The work itself runs in a background task, so the control plane's call returns
in milliseconds no matter how slow vnstock is that morning.
"""

from __future__ import annotations

from fastapi import BackgroundTasks, Depends
from kactus_common.portfolio.schema import (
    CrawlJobSchema,
    CrawlRequest,
    CrawlStatusSchema,
    CrawlTriggerResponse,
)
from kactus_common.router import KactusAPIRouter
from kactus_data.jobs.crawl import run_crawl, sync_catalog
from kactus_data.sources.stock.auth import _safe_tier_name
from kactus_data_plane.runtime import get_runtime
from kactus_data_plane.security import require_service_token

router = KactusAPIRouter(
    prefix="/internal",
    tags=["internal-jobs"],
    dependencies=[Depends(require_service_token)],
)


@router.post("/crawl")
async def trigger_crawl(
    body: CrawlRequest, background: BackgroundTasks
) -> CrawlTriggerResponse:
    """Queue a crawl of ``kind`` and return immediately.

    With ``codes_by_type`` omitted the data plane crawls the live watchlist
    union it computes from Postgres itself.

    ``dedup`` is enforced inside ``run_crawl`` against the ``CrawlRun`` table,
    which is the authoritative in-flight marker — shared Postgres, so it holds
    across both planes and survives a restart of either.
    """
    runtime = get_runtime()
    background.add_task(
        run_crawl,
        db=runtime.db,
        providers=runtime.providers,
        kind=body.kind,
        codes_by_type=body.codes_by_type,
        symbol_provider=None if body.codes_by_type else runtime.symbol_provider,
        trigger=body.trigger,
        portfolio_id=body.portfolio_id,
        dedup=body.dedup,
    )
    return CrawlTriggerResponse(skipped=False, message=f"Crawl '{body.kind}' scheduled")


@router.post("/catalog/sync")
async def trigger_catalog_sync(background: BackgroundTasks) -> CrawlTriggerResponse:
    """Refresh the supported-asset catalog for every provider."""
    runtime = get_runtime()
    background.add_task(sync_catalog, db=runtime.db, providers=runtime.providers)
    return CrawlTriggerResponse(skipped=False, message="Catalog sync scheduled")


@router.get("/scheduler/status")
async def scheduler_status() -> CrawlStatusSchema:
    """Scheduler + vnstock tier snapshot, for the control plane's admin view."""
    scheduler = get_runtime().scheduler
    jobs: list[CrawlJobSchema] = []
    running = False
    if scheduler is not None:
        running = scheduler.running
        for job in scheduler.get_jobs():
            nrt = getattr(job, "next_run_time", None)
            trigger = getattr(job, "trigger", None)
            jobs.append(
                CrawlJobSchema(
                    id=job.id,
                    name=job.name or job.id,
                    cadence=str(trigger) if trigger is not None else None,
                    next_run_time=nrt.isoformat() if nrt else None,
                    # APScheduler marks a paused job by clearing next_run_time
                    # while the scheduler itself keeps running.
                    paused=running and nrt is None,
                )
            )
    return CrawlStatusSchema(
        scheduler_running=running, vnstock_tier=_safe_tier_name(), jobs=jobs
    )
