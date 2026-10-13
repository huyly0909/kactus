"""Crawl queue handlers — every crawl executes as a ``SyncJob``.

Importing this module registers one handler per crawl job type
(``stock_quotes`` … ``gold_quotes``, ``stock_ohlcv``, ``catalog_sync``) into
:data:`kactus_data.jobs.sync_queue.SYNC_HANDLERS`.  The naming contract lives
in :mod:`kactus_common.portfolio.crawl_queue` (both planes enqueue with it).

A vnstock rate-limit hit finishes the job FAILED with the full reason — codes
completed, budget, partial rows stored — while the partial data stays in
DuckDB (the provider stores before raising :class:`RateLimitedError`).
"""

from __future__ import annotations

from kactus_common.config import settings
from kactus_common.portfolio.const import AssetType, CrawlKind
from kactus_common.portfolio.crawl_queue import (
    CATALOG_JOB_TYPE,
    CRAWL_KIND_ASSET_TYPES,
    crawl_job_type,
)
from kactus_data.exceptions import RateLimitedError
from kactus_data.jobs.crawl import (
    _emit_refreshed,
    crawl_ohlcv_blocking,
    guarded_to_thread,
    sync_catalog,
)
from kactus_data.jobs.sync_queue import (
    ProgressFn,
    SyncJobDeps,
    SyncJobView,
    register_handler,
)
from kactus_data.sources.stock.auth import _active_rpm
from loguru import logger


async def _resolve_codes(
    view: SyncJobView, deps: SyncJobDeps, asset_type: AssetType
) -> list[str]:
    """Explicit ``params.codes``, else the live watchlist union for the type."""
    codes = view.params.get("codes")
    if codes:
        return [str(c).upper() for c in codes]
    if deps.symbol_provider is None:
        return []
    by_type = await deps.symbol_provider.get_codes_by_type()
    return by_type.get(str(asset_type), [])


def _rate_limit_message(ex: RateLimitedError) -> str:
    return (
        f"vnstock rate limit ({_active_rpm()} req/min) after "
        f"{ex.done}/{ex.total} codes — stored {ex.rows_stored} partial rows"
    )


def _make_crawl_handler(asset_type: AssetType, kind: CrawlKind):
    async def _handler(
        view: SyncJobView, deps: SyncJobDeps, on_progress: ProgressFn
    ) -> dict:
        provider = deps.providers.get(asset_type)
        if provider is None or kind not in provider.supported_kinds():
            raise ValueError(f"No provider crawls {asset_type}:{kind}")
        codes = await _resolve_codes(view, deps, asset_type)
        if not codes:
            logger.info(f"Crawl {asset_type}:{kind} — empty watchlist, nothing to do")
            return {"total": 0, "rows": 0, "codes": []}

        await on_progress(0, len(codes))
        try:
            if kind == CrawlKind.OHLCV:
                data_source = getattr(settings, "data_source", "VCI")
                rows = await guarded_to_thread(
                    lambda: crawl_ohlcv_blocking(
                        deps.storage, codes, data_source=data_source
                    )
                )
            else:
                rows = await guarded_to_thread(provider.crawl, kind, codes)
        except RateLimitedError as ex:
            # The provider stored the partial frame before raising; the data
            # changed, so still nudge the SSE clients before failing the job.
            if ex.rows_stored:
                await _emit_refreshed(
                    asset_type=str(asset_type), kind=str(kind), codes=codes
                )
            await on_progress(ex.done, ex.total)
            raise RuntimeError(_rate_limit_message(ex)) from ex

        if rows:
            await _emit_refreshed(
                asset_type=str(asset_type), kind=str(kind), codes=codes
            )
        logger.info(f"Crawl {asset_type}:{kind} wrote {rows} rows")
        return {"total": len(codes), "rows": rows, "codes": codes}

    return _handler


async def catalog_sync_handler(
    view: SyncJobView, deps: SyncJobDeps, on_progress: ProgressFn
) -> dict:
    """Refresh the supported-asset catalog across every provider."""
    out = await sync_catalog(db=deps.db, providers=deps.providers)
    total = len(out)
    await on_progress(total, total)
    return {"total": total, **out}


def register_crawl_handlers() -> None:
    """Bind every crawl job type to its handler (idempotent)."""
    for kind, asset_types in CRAWL_KIND_ASSET_TYPES.items():
        for asset_type in asset_types:
            register_handler(crawl_job_type(asset_type, kind))(
                _make_crawl_handler(asset_type, kind)
            )
    register_handler(CATALOG_JOB_TYPE)(catalog_sync_handler)


register_crawl_handlers()
