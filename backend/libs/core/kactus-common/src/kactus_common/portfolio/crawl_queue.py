"""Crawl-job enqueue helpers — the single owner of crawl job naming.

Every crawl (cron scheduler, admin run-now, portfolio refresh) executes as a
``SyncJob`` so one system captures the full lifecycle: enqueue = the PENDING
ack (``create_time`` = trigger instant, ``params`` = what, ``created_by`` =
who), claim = RUNNING, finish = SUCCESS/FAILED with a full reason.

Job types follow ``{asset}_{kind}`` (``stock_news``, ``gold_quotes``) so the
queue UI's family filter (``gold_%`` / ``stock_%``) covers them for free; the
dedup key is the active-uniqueness marker that replaces the old
``CrawlRun.has_inflight`` probe.  This module lives in core because both
planes enqueue: kactus-fin inserts directly into the shared Postgres (same
pattern as the gold admin API) and the data plane's scheduler does the same.
"""

from __future__ import annotations

from kactus_common.sync.model import SyncJob
from kactus_common.sync.service import SyncJobService
from sqlalchemy.ext.asyncio import AsyncSession

from .const import AssetType, CrawlKind, CrawlTrigger

#: Catalog refresh is one job across all providers, not per asset type.
CATALOG_JOB_TYPE = "catalog_sync"
CATALOG_DEDUP_KEY = "catalog:all"

#: Which asset types produce each crawl kind — the static contract both planes
#: agree on (gold has quotes only; everything else is stock).  ``COIN`` joins
#: here when a provider lands.
CRAWL_KIND_ASSET_TYPES: dict[CrawlKind, tuple[AssetType, ...]] = {
    CrawlKind.QUOTES: (AssetType.STOCK, AssetType.GOLD),
    CrawlKind.NEWS: (AssetType.STOCK,),
    CrawlKind.RATIOS: (AssetType.STOCK,),
    CrawlKind.EVENTS: (AssetType.STOCK,),
    CrawlKind.OHLCV: (AssetType.STOCK,),
}


def crawl_job_type(asset_type: AssetType, kind: CrawlKind) -> str:
    """``stock_quotes`` / ``gold_quotes`` / … — matches the family filter."""
    return f"{str(asset_type).lower()}_{kind}"


def crawl_dedup_key(asset_type: AssetType, kind: CrawlKind) -> str:
    return f"crawl:{str(asset_type).lower()}:{kind}"


async def enqueue_crawl_jobs(
    session: AsyncSession,
    *,
    kind: CrawlKind,
    codes_by_type: dict[str, list[str]] | None = None,
    trigger: CrawlTrigger = CrawlTrigger.MANUAL,
    portfolio_id: int | None = None,
) -> tuple[list[SyncJob], list[SyncJob]]:
    """Enqueue one crawl job per asset type producing ``kind``.

    ``codes_by_type=None`` means "the live watchlist union" — the handler
    resolves it at run time, so a job that waits in the queue crawls the
    current watchlist, not a stale snapshot.  Returns ``(created, existing)``;
    an ``existing`` entry is the live job that made the enqueue a no-op.
    """
    created: list[SyncJob] = []
    existing: list[SyncJob] = []
    for asset_type in CRAWL_KIND_ASSET_TYPES.get(kind, ()):
        codes: list[str] | None = None
        if codes_by_type is not None:
            codes = codes_by_type.get(str(asset_type))
            if not codes:
                continue
        params: dict = {"codes": codes, "trigger": str(trigger)}
        if portfolio_id is not None:
            params["portfolio_id"] = portfolio_id
        job, was_created = await SyncJobService.enqueue(
            session,
            job_type=crawl_job_type(asset_type, kind),
            params=params,
            dedup_key=crawl_dedup_key(asset_type, kind),
        )
        (created if was_created else existing).append(job)
    return created, existing


async def enqueue_catalog_sync(
    session: AsyncSession, *, trigger: CrawlTrigger = CrawlTrigger.MANUAL
) -> tuple[SyncJob, bool]:
    """Enqueue the supported-asset catalog refresh (all providers, one job)."""
    return await SyncJobService.enqueue(
        session,
        job_type=CATALOG_JOB_TYPE,
        params={"trigger": str(trigger)},
        dedup_key=CATALOG_DEDUP_KEY,
    )
