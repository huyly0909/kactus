"""Async crawl orchestration — portfolio-ignorant ETL jobs.

These jobs take codes (directly or via an injected :class:`SymbolProvider`), call
the matching :class:`AssetProvider` for the blocking vnstock+DuckDB work off the
event loop (``asyncio.to_thread``), record a :class:`CrawlRun`, and emit a
``data_refreshed`` event so the SSE layer can nudge browsers.

Concurrency across asset types is gated by a semaphore sized from the active
vnstock tier.  The job layer never imports kactus-fin — the union of watchlist
codes arrives through the ``SymbolProvider`` seam (defined in kactus-common).
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.portfolio.const import (
    AssetType,
    CrawlKind,
    CrawlStatus,
    CrawlTrigger,
)
from kactus_common.portfolio.events import MarketDataRefreshedPayload
from kactus_common.portfolio.service import CrawlRunService, SupportedAssetService
from kactus_common.portfolio.symbol_provider import SymbolProvider
from kactus_data.portfolio.provider import AssetProvider
from kactus_data.sources.stock.auth import vnstock_max_concurrency
from kactus_data.storage.duckdb import DuckDBStorage
from loguru import logger


async def _emit_refreshed(
    *, asset_type: str, kind: str, codes: list[str], crawl_run_id: int | None
) -> None:
    """Foreground (blinker) dispatch — crawls run outside a request.

    ``background=True`` would route through fastapi-events, which is a no-op
    outside a request context.  A missing handler raises ``KeyError`` in blinker
    (e.g. standalone CLI with no SSE wired) — that is benign, not a failure.
    """
    payload = MarketDataRefreshedPayload(
        asset_type=asset_type, kind=kind, codes=codes, crawl_run_id=crawl_run_id
    )
    try:
        await payload.dispatch(background=False)
    except KeyError:
        logger.debug("No SSE handler registered — skipping data_refreshed dispatch")
    except Exception as ex:  # pragma: no cover - defensive
        logger.warning(f"data_refreshed dispatch failed: {ex}")


async def _crawl_one(
    *,
    db: DatabaseSessionManager,
    provider: AssetProvider,
    asset_type: AssetType,
    kind: CrawlKind,
    codes: list[str],
    trigger: CrawlTrigger,
    portfolio_id: int | None,
    dedup: bool,
    sem: asyncio.Semaphore,
) -> int | None:
    """Crawl one (asset_type, kind); returns the CrawlRun id (or None if deduped)."""
    async with db.get_session() as session:
        if dedup and await CrawlRunService.has_inflight(
            session, asset_type=asset_type, kind=kind
        ):
            logger.info(f"Skip {asset_type}:{kind} — a crawl is already in-flight")
            return None
        run = await CrawlRunService.start(
            session,
            asset_type=asset_type,
            kind=kind,
            trigger=trigger,
            portfolio_id=portfolio_id,
        )
        run_id = run.id
        ok = False
        try:
            async with sem:
                rows = await asyncio.to_thread(provider.crawl, kind, codes)
            await CrawlRunService.finish(
                session, run, rows_written=rows, status=CrawlStatus.SUCCESS
            )
            ok = True
            logger.info(f"Crawl {asset_type}:{kind} wrote {rows} rows")
        except Exception as ex:
            logger.exception(f"Crawl {asset_type}:{kind} failed")
            await CrawlRunService.finish(
                session, run, status=CrawlStatus.ERROR, error=str(ex)
            )
    if ok:
        await _emit_refreshed(
            asset_type=str(asset_type), kind=str(kind), codes=codes, crawl_run_id=run_id
        )
    return run_id


async def run_crawl(
    *,
    db: DatabaseSessionManager,
    providers: dict[AssetType, AssetProvider],
    kind: CrawlKind,
    codes_by_type: dict[str, list[str]] | None = None,
    symbol_provider: SymbolProvider | None = None,
    trigger: CrawlTrigger = CrawlTrigger.CRON,
    portfolio_id: int | None = None,
    dedup: bool = False,
) -> list[int]:
    """Crawl ``kind`` for the code union, grouped by asset type.

    Provide ``codes_by_type`` directly (CLI / manual refresh of a known set) or a
    ``symbol_provider`` (scheduler — computes the live union).  Returns the ids of
    the crawl runs that executed (deduped ones are omitted).
    """
    if codes_by_type is None:
        if symbol_provider is None:
            raise ValueError("run_crawl requires codes_by_type or symbol_provider")
        codes_by_type = await symbol_provider.get_codes_by_type()

    sem = asyncio.Semaphore(vnstock_max_concurrency())
    tasks = []
    for at_str, codes in codes_by_type.items():
        asset_type = AssetType(at_str)
        provider = providers.get(asset_type)
        if provider is None or kind not in provider.supported_kinds() or not codes:
            continue
        tasks.append(
            _crawl_one(
                db=db,
                provider=provider,
                asset_type=asset_type,
                kind=kind,
                codes=codes,
                trigger=trigger,
                portfolio_id=portfolio_id,
                dedup=dedup,
                sem=sem,
            )
        )
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


async def sync_catalog(
    *,
    db: DatabaseSessionManager,
    providers: dict[AssetType, AssetProvider],
    asset_types: list[AssetType] | None = None,
) -> dict[str, int]:
    """Refresh the supported-asset catalog for each (selected) provider."""
    out: dict[str, int] = {}
    for asset_type, provider in providers.items():
        if asset_types and asset_type not in asset_types:
            continue
        entries = await asyncio.to_thread(provider.fetch_catalog)
        async with db.get_session() as session:
            written = await SupportedAssetService.upsert_many(
                session, asset_type=asset_type, entries=entries
            )
        out[str(asset_type)] = written
        logger.info(f"Catalog sync {asset_type}: {written} entries")
    return out


async def crawl_ohlcv(
    *,
    db: DatabaseSessionManager,
    storage: DuckDBStorage,
    codes: list[str],
    data_source: str = "VCI",
    days: int = 7,
    trigger: CrawlTrigger = CrawlTrigger.CRON,
    portfolio_id: int | None = None,
) -> int | None:
    """Backfill recent daily OHLCV for ``codes`` via the existing pipeline."""
    if not codes:
        return None
    end = date.today()
    start = end - timedelta(days=days)

    def _do() -> int:
        from kactus_data.pipeline import SyncPipeline
        from kactus_data.sources.stock.tables import STOCK_OHLCV_TABLE
        from kactus_data.sources.stock.vnstock import VnstockOHLCVSource

        pipeline = SyncPipeline(
            VnstockOHLCVSource(source=data_source, interval="1D"), storage
        )
        total = 0
        for code in codes:
            total += pipeline.run(STOCK_OHLCV_TABLE, code, start, end).rows_stored
        return total

    async with db.get_session() as session:
        run = await CrawlRunService.start(
            session,
            asset_type=AssetType.STOCK,
            kind=CrawlKind.OHLCV,
            trigger=trigger,
            portfolio_id=portfolio_id,
        )
        run_id = run.id
        ok = False
        try:
            rows = await asyncio.to_thread(_do)
            await CrawlRunService.finish(
                session, run, rows_written=rows, status=CrawlStatus.SUCCESS
            )
            ok = True
        except Exception as ex:
            logger.exception("OHLCV crawl failed")
            await CrawlRunService.finish(
                session, run, status=CrawlStatus.ERROR, error=str(ex)
            )
    if ok:
        await _emit_refreshed(
            asset_type=str(AssetType.STOCK),
            kind=str(CrawlKind.OHLCV),
            codes=codes,
            crawl_run_id=run_id,
        )
    return run_id
