"""APScheduler wiring for the portfolio crawler.

In-process ``AsyncIOScheduler`` (single-worker v1).  Cadence:

* live quotes  — hourly, Mon–Fri 09:00–15:00 (Asia/Ho_Chi_Minh)
* news         — hourly, Mon–Fri 09:00–15:00 (offset 5')
* ratios / events — daily after close (~15:30+)
* OHLCV        — daily after close
* catalog sync — daily pre-open (~08:30)

All jobs pull the live code union from the injected ``SymbolProvider`` so they
crawl exactly what users watch.  ``build_scheduler`` only constructs; the caller
(kactus-fin lifespan) ``.start()``s it on the running loop — AFTER registering
the SSE handler, else the foreground dispatch hits a blinker ``KeyError``.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.portfolio.const import AssetType, CrawlKind
from kactus_common.portfolio.symbol_provider import SymbolProvider
from kactus_data.jobs.crawl import crawl_ohlcv, run_crawl, sync_catalog
from kactus_data.portfolio.provider import AssetProvider
from kactus_data.storage.duckdb import DuckDBStorage
from loguru import logger

DEFAULT_TZ = "Asia/Ho_Chi_Minh"


def build_scheduler(
    *,
    db: DatabaseSessionManager,
    providers: dict[AssetType, AssetProvider],
    symbol_provider: SymbolProvider,
    storage: DuckDBStorage | None = None,
    data_source: str = "VCI",
    timezone: str = DEFAULT_TZ,
) -> AsyncIOScheduler:
    """Build (but do not start) the portfolio crawl scheduler."""
    scheduler = AsyncIOScheduler(timezone=timezone)

    async def _crawl(kind: CrawlKind) -> None:
        await run_crawl(
            db=db, providers=providers, kind=kind, symbol_provider=symbol_provider
        )

    def _biz(minute: int, hour: str = "9-15") -> CronTrigger:
        return CronTrigger(
            day_of_week="mon-fri", hour=hour, minute=minute, timezone=timezone
        )

    # Intraday: live quotes + news, hourly during the session.
    scheduler.add_job(
        _crawl, _biz(0), args=[CrawlKind.QUOTES], id="crawl_quotes", replace_existing=True
    )
    scheduler.add_job(
        _crawl, _biz(5), args=[CrawlKind.NEWS], id="crawl_news", replace_existing=True
    )
    # After close: decision-support datasets.
    # NOTE: foreign_trade is intentionally not scheduled — VCI (vnstock 4.x) does
    # not implement foreign-flow; it was only served by the now-dead TCBS provider.
    scheduler.add_job(
        _crawl, _biz(35, hour="15"), args=[CrawlKind.RATIOS],
        id="crawl_ratios", replace_existing=True,
    )
    scheduler.add_job(
        _crawl, _biz(40, hour="15"), args=[CrawlKind.EVENTS],
        id="crawl_events", replace_existing=True,
    )

    # OHLCV daily after close (reuses the existing per-code OHLCV pipeline).
    if storage is not None:
        async def _ohlcv() -> None:
            codes_by_type = await symbol_provider.get_codes_by_type()
            stock_codes = codes_by_type.get(str(AssetType.STOCK), [])
            await crawl_ohlcv(
                db=db, storage=storage, codes=stock_codes, data_source=data_source
            )

        scheduler.add_job(
            _ohlcv, _biz(45, hour="15"), id="crawl_ohlcv", replace_existing=True
        )

    # Pre-open daily catalog refresh.
    async def _catalog() -> None:
        await sync_catalog(db=db, providers=providers)

    scheduler.add_job(
        _catalog, CronTrigger(hour=8, minute=30, timezone=timezone),
        id="sync_catalog", replace_existing=True,
    )

    logger.info(f"Portfolio scheduler built with {len(scheduler.get_jobs())} jobs")
    return scheduler
