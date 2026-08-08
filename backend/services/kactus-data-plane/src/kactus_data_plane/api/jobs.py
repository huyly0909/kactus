"""``/internal/crawl``, ``/internal/catalog/sync``, ``/internal/scheduler/status``.

Commands, not events — deliberately HTTP rather than a Redis queue. A crawl
trigger has a caller who wants to know whether it was accepted or deduped, and
a status code, a timeout and a stack trace are the cheapest way to tell them.

A trigger *enqueues* a ``SyncJob`` (PENDING ack) that the single dispatcher
executes FIFO, so the response can report the real dedup outcome: ``skipped``
means every requested job was already PENDING/RUNNING.
"""

from __future__ import annotations

from fastapi import Depends
from kactus_common.portfolio.crawl_queue import enqueue_catalog_sync, enqueue_crawl_jobs
from kactus_common.portfolio.schema import (
    CrawlJobSchema,
    CrawlRequest,
    CrawlStatusSchema,
    CrawlTriggerResponse,
)
from kactus_common.router import KactusAPIRouter
from kactus_data.sources.stock.auth import _safe_tier_name
from kactus_data_plane.runtime import get_runtime
from kactus_data_plane.security import require_service_token

router = KactusAPIRouter(
    prefix="/internal",
    tags=["internal-jobs"],
    dependencies=[Depends(require_service_token)],
)


@router.post("/crawl")
async def trigger_crawl(body: CrawlRequest) -> CrawlTriggerResponse:
    """Enqueue a crawl of ``kind`` and return the ack.

    With ``codes_by_type`` omitted the handler crawls the live watchlist union
    it computes from Postgres at run time.
    """
    runtime = get_runtime()
    async with runtime.db.get_session() as session:
        created, existing = await enqueue_crawl_jobs(
            session,
            kind=body.kind,
            codes_by_type=body.codes_by_type,
            trigger=body.trigger,
            portfolio_id=body.portfolio_id,
        )
    if not created:
        message = (
            f"Crawl '{body.kind}' already queued/running"
            if existing
            else f"No asset type produces '{body.kind}'"
        )
        return CrawlTriggerResponse(skipped=True, message=message)
    return CrawlTriggerResponse(
        job_ids=[j.id for j in created],
        skipped=False,
        message=f"Crawl '{body.kind}' queued",
    )


@router.post("/catalog/sync")
async def trigger_catalog_sync() -> CrawlTriggerResponse:
    """Enqueue the supported-asset catalog refresh (all providers)."""
    runtime = get_runtime()
    async with runtime.db.get_session() as session:
        job, created = await enqueue_catalog_sync(session)
    if not created:
        return CrawlTriggerResponse(
            skipped=True, message="Catalog sync already queued/running"
        )
    return CrawlTriggerResponse(
        job_ids=[job.id], skipped=False, message="Catalog sync queued"
    )


def _cron_fields(trigger: object) -> dict[str, str] | None:
    """A cron trigger's fields as ``{name: expression}``, else ``None``.

    Duck-typed on ``.fields`` so an interval/date trigger simply yields ``None``
    and the client falls back to ``cadence``. Wildcards and a zero ``second``
    are dropped: what survives is exactly what a human would say out loud, and
    ``day_of_week`` being *absent* is what tells the UI a job runs weekends too.
    """
    fields = getattr(trigger, "fields", None)
    if not fields:
        return None
    out = {f.name: str(f) for f in fields}
    if out.get("second") == "0":
        out.pop("second")
    return {name: expr for name, expr in out.items() if expr != "*"}


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
                    cron=_cron_fields(trigger),
                    timezone=(
                        str(tz) if (tz := getattr(trigger, "timezone", None)) else None
                    ),
                    next_run_time=nrt.isoformat() if nrt else None,
                    # APScheduler marks a paused job by clearing next_run_time
                    # while the scheduler itself keeps running.
                    paused=running and nrt is None,
                )
            )
    return CrawlStatusSchema(
        scheduler_running=running, vnstock_tier=_safe_tier_name(), jobs=jobs
    )
