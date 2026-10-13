"""APScheduler wiring for the portfolio crawler.

In-process ``AsyncIOScheduler`` (single-worker v1).  Cadence:

* live quotes  — hourly, Mon–Fri 09:00–15:00 (Asia/Ho_Chi_Minh)
* news         — hourly, Mon–Fri 09:00–15:00 (offset 5')
* ratios / events — daily after close (~15:30+)
* OHLCV        — daily after close
* catalog sync — daily pre-open (~08:30)

A cron fire only *enqueues*: each crawl becomes a PENDING ``SyncJob``
(``params.trigger = "cron"``, ``create_time`` = the fire instant) that the
single dispatcher executes FIFO — one tracking system for every trigger, and
the serial queue keeps concurrent crawls from ganging up on the shared
vnstock budget.  Codes are resolved by the handler at run time (live
watchlist union).  Dedup is the queue's active-unique ``dedup_key``: a fire
that lands while the previous job is still PENDING/RUNNING is a logged no-op.

``build_scheduler`` only constructs; the caller (data-plane lifespan)
``.start()``s it on the running loop.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.portfolio.const import CrawlKind, CrawlTrigger
from kactus_common.portfolio.crawl_queue import enqueue_catalog_sync, enqueue_crawl_jobs
from loguru import logger

DEFAULT_TZ = "Asia/Ho_Chi_Minh"


def build_scheduler(
    *,
    db: DatabaseSessionManager,
    timezone: str = DEFAULT_TZ,
) -> AsyncIOScheduler:
    """Build (but do not start) the portfolio crawl scheduler."""
    scheduler = AsyncIOScheduler(timezone=timezone)

    async def _crawl(kind: CrawlKind) -> None:
        async with db.get_session() as session:
            created, existing = await enqueue_crawl_jobs(
                session, kind=kind, trigger=CrawlTrigger.CRON
            )
        for job in created:
            logger.info(f"Queued crawl job {job.job_type} (job {job.id})")
        for job in existing:
            logger.info(f"Skip {job.job_type} — already queued/running (job {job.id})")

    def _biz(minute: int, hour: str = "9-15") -> CronTrigger:
        return CronTrigger(
            day_of_week="mon-fri", hour=hour, minute=minute, timezone=timezone
        )

    # Every ``add_job`` passes an explicit ``name``: APScheduler otherwise
    # derives it from the callable, and ``_crawl`` is a closure — the admin view
    # would read "build_scheduler.<locals>._crawl" for five of the six jobs.

    # Intraday: live quotes + news, hourly during the session.
    scheduler.add_job(
        _crawl,
        _biz(0),
        args=[CrawlKind.QUOTES],
        id="crawl_quotes",
        name="Crawl quotes",
        replace_existing=True,
    )
    scheduler.add_job(
        _crawl,
        _biz(5),
        args=[CrawlKind.NEWS],
        id="crawl_news",
        name="Crawl news",
        replace_existing=True,
    )
    # After close: decision-support datasets.
    # NOTE: foreign_trade is intentionally not scheduled — VCI (vnstock 4.x) does
    # not implement foreign-flow; it was only served by the now-dead TCBS provider.
    scheduler.add_job(
        _crawl,
        _biz(35, hour="15"),
        args=[CrawlKind.RATIOS],
        id="crawl_ratios",
        name="Crawl ratios",
        replace_existing=True,
    )
    scheduler.add_job(
        _crawl,
        _biz(40, hour="15"),
        args=[CrawlKind.EVENTS],
        id="crawl_events",
        name="Crawl events",
        replace_existing=True,
    )
    # OHLCV daily after close (per-code history via the existing pipeline).
    scheduler.add_job(
        _crawl,
        _biz(45, hour="15"),
        args=[CrawlKind.OHLCV],
        id="crawl_ohlcv",
        name="Crawl OHLCV",
        replace_existing=True,
    )

    # Pre-open daily catalog refresh.
    async def _catalog() -> None:
        async with db.get_session() as session:
            job, created = await enqueue_catalog_sync(
                session, trigger=CrawlTrigger.CRON
            )
        if created:
            logger.info(f"Queued catalog sync (job {job.id})")
        else:
            logger.info(f"Skip catalog sync — already queued/running (job {job.id})")

    scheduler.add_job(
        _catalog,
        # No ``day_of_week``: the catalog refreshes every day, weekends included.
        CronTrigger(hour=8, minute=30, timezone=timezone),
        id="sync_catalog",
        name="Catalog sync",
        replace_existing=True,
    )

    logger.info(f"Portfolio scheduler built with {len(scheduler.get_jobs())} jobs")
    return scheduler
