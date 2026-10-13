"""Blocking crawl primitives shared by the queue handlers and the CLI.

Crawl *tracking* lives in the sync queue (see :mod:`crawl_handlers`); this
module holds the pieces that actually do work: the SystemExit-safe thread
wrapper, the SSE nudge, the catalog refresh and the paced OHLCV backfill.
``CrawlRun`` is retired — the queue rows are the audit trail now.
"""

from __future__ import annotations

import asyncio
import time
from datetime import date, timedelta

from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.portfolio.const import AssetType
from kactus_common.portfolio.events import MarketDataRefreshedPayload
from kactus_common.portfolio.service import SupportedAssetService
from kactus_data.exceptions import RateLimitedError
from kactus_data.pipeline import SyncPipeline
from kactus_data.portfolio.provider import AssetProvider
from kactus_data.sources.stock.auth import vnstock_min_interval
from kactus_data.sources.stock.tables import STOCK_OHLCV_TABLE
from kactus_data.sources.stock.vnstock import VnstockOHLCVSource
from kactus_data.storage.duckdb import DuckDBStorage
from loguru import logger


async def guarded_to_thread(fn, /, *args):
    """``asyncio.to_thread``, but ``SystemExit`` becomes ``RuntimeError``.

    vnai's rate-limit guard calls ``sys.exit(...)``; ``SystemExit`` is a
    ``BaseException`` that sails past every ``except Exception`` and kills the
    event loop (this took the whole data plane down once).  Converted inside
    the worker thread, a rate-limit hit is just a failed job.
    """

    def _guard():
        try:
            return fn(*args)
        except SystemExit as exc:
            raise RuntimeError(f"vnstock aborted: {exc}") from exc

    return await asyncio.to_thread(_guard)


async def _emit_refreshed(
    *, asset_type: str, kind: str, codes: list[str], crawl_run_id: int | None = None
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
        entries = await guarded_to_thread(provider.fetch_catalog)
        async with db.get_session() as session:
            written = await SupportedAssetService.upsert_many(
                session, asset_type=asset_type, entries=entries
            )
        out[str(asset_type)] = written
        logger.info(f"Catalog sync {asset_type}: {written} entries")
    return out


def crawl_ohlcv_blocking(
    storage: DuckDBStorage,
    codes: list[str],
    *,
    data_source: str = "VCI",
    days: int = 7,
) -> int:
    """Backfill recent daily OHLCV per code, paced to the vnstock budget.

    Blocking — run via :func:`guarded_to_thread`.  A rate-limit hit raises
    :class:`RateLimitedError` with the rows already stored (each code stores as
    it completes, so partial progress is durable).
    """
    end = date.today()
    start = end - timedelta(days=days)
    pipeline = SyncPipeline(
        VnstockOHLCVSource(source=data_source, interval="1D"), storage
    )
    interval = vnstock_min_interval()
    total = 0
    for i, code in enumerate(codes):
        if i:
            time.sleep(interval)
        try:
            total += pipeline.run(STOCK_OHLCV_TABLE, code, start, end).rows_stored
        except SystemExit as ex:
            logger.warning(
                f"ohlcv: vnstock rate limited at {code} ({i}/{len(codes)} done): {ex}"
            )
            raise RateLimitedError(done=i, total=len(codes), rows_stored=total) from ex
    return total
