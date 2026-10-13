"""kactus-data-plane application factory + lifespan.

Boots the ETL side of the platform: vnstock auth, the DuckDB handle, the asset
providers, the SSE bridge and the crawl scheduler — in that order, because the
scheduler may fire before the first request and the SSE handler has to be
registered before it does (blinker raises ``KeyError`` on a foreground dispatch
with no handler attached).
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from kactus_common.database.oltp.session import get_db
from kactus_common.exceptions import install_exception_handlers
from kactus_common.redis.client import close_redis
from kactus_common.sse.broker import get_sse_broker, reset_sse_broker
from kactus_common.sse.market import register_sse_handler
from kactus_data.jobs.scheduler import build_scheduler
from kactus_data.jobs.sync_queue import SyncJobDeps, run_dispatcher
from kactus_data.portfolio.provider import build_providers
from kactus_data.sources.stock.auth import init_vnstock_auth
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_data_plane.api.assets import router as assets_router
from kactus_data_plane.api.health import router as health_router
from kactus_data_plane.api.imports import router as imports_router
from kactus_data_plane.api.jobs import router as jobs_router
from kactus_data_plane.api.market import router as market_router
from kactus_data_plane.config import get_settings
from kactus_data_plane.runtime import DataRuntime, set_runtime
from kactus_data_plane.symbol_provider import WatchlistSymbolProvider
from loguru import logger


def _detected_worker_count() -> int | None:
    """Best-effort read of how many web workers this process was launched with.

    Returns ``None`` when it cannot tell — uvicorn/gunicorn expose no reliable
    marker inside a spawned child, so this only catches the common launch forms
    (``--workers N`` on the command line, or the ``WEB_CONCURRENCY`` env var both
    servers honour). A miss means no warning, never a false alarm.
    """
    concurrency = os.environ.get("WEB_CONCURRENCY")
    if concurrency and concurrency.isdigit():
        return int(concurrency)
    for flag in ("--workers", "-w"):
        if flag in sys.argv:
            value = sys.argv[sys.argv.index(flag) + 1 :][:1]
            if value and value[0].isdigit():
                return int(value[0])
    return None


def _warn_if_misconfigured(settings) -> None:
    """Shout about the two ways this service can be deployed into a broken state.

    Neither raises. A data plane that refuses to boot crawls nothing at all,
    which is strictly worse than one that crawls twice; the operator gets to
    decide. Both conditions are visible in ``/health``.
    """
    workers = _detected_worker_count()
    if workers is not None and workers > 1:
        logger.warning(
            f"kactus-data-plane looks like it is running with {workers} workers. "
            "This service must run at exactly one worker and one replica: each "
            "process would open its own DuckDB write handle (IOException on the "
            "lock file) and run its own copy of the scheduler (duplicate crawls, "
            "N× the vnstock rate-limit budget). Use --workers 1."
        )

    if getattr(settings, "coordination_backend", "memory") != "redis":
        logger.warning(
            "KACTUS_COORDINATION_BACKEND is not 'redis'. Crawl completions will "
            "be published to this process's in-memory broker and no kactus-fin "
            "client will ever see them — the two planes are separate processes "
            "by construction, so the browser SSE stream will sit silent. Set "
            "KACTUS_COORDINATION_BACKEND=redis on both services."
        )


def build_runtime(settings) -> DataRuntime:
    """Authenticate vnstock, open DuckDB, build providers, start the scheduler."""
    init_vnstock_auth()

    db = get_db()
    storage = DuckDBStorage(settings.db_path)
    providers = build_providers(
        storage,
        data_source=settings.data_source,
        mihong_token=getattr(settings, "mihong_xsrf_token", ""),
    )
    symbol_provider = WatchlistSymbolProvider(db)

    # MUST precede scheduler start (blinker KeyError otherwise).
    register_sse_handler()

    scheduler = None
    if getattr(settings, "enable_portfolio_scheduler", True):
        scheduler = build_scheduler(db=db)
        try:
            scheduler.start()
        except Exception as ex:  # pragma: no cover - defensive
            logger.warning(f"Portfolio scheduler failed to start: {ex}")
            scheduler = None

    runtime = DataRuntime(
        db=db,
        providers=providers,
        storage=storage,
        symbol_provider=symbol_provider,
        scheduler=scheduler,
    )
    set_runtime(runtime)
    logger.info(f"Data runtime initialised (scheduler={'on' if scheduler else 'off'})")
    return runtime


def shutdown_runtime(runtime: DataRuntime | None) -> None:
    if runtime is not None and runtime.scheduler is not None:
        try:
            runtime.scheduler.shutdown(wait=False)
        except Exception:  # pragma: no cover - defensive
            pass
    set_runtime(None)


def start_dispatcher(runtime: DataRuntime) -> asyncio.Event:
    """Launch the single sync-job dispatcher on the running loop.

    Runs unconditionally (independent of the crawl scheduler): this process is
    the sole DuckDB writer, so it is the only place a queued write can execute.
    Gold handlers register on import of ``kactus_data.jobs.gold_sync``; crawl
    handlers on import of ``kactus_data.jobs.crawl_handlers``.
    """
    import kactus_data.jobs.crawl_handlers  # noqa: F401 — registers crawl handlers
    import kactus_data.jobs.gold_sync  # noqa: F401 — registers GOLD_* handlers

    stop_event = asyncio.Event()
    deps = SyncJobDeps(
        db=runtime.db,
        storage=runtime.storage,
        providers=runtime.providers,
        symbol_provider=runtime.symbol_provider,
    )
    runtime.sync_dispatcher = asyncio.create_task(
        run_dispatcher(deps, stop_event=stop_event)
    )
    runtime._extra["sync_stop_event"] = stop_event
    return stop_event


async def stop_dispatcher(runtime: DataRuntime, stop_event: asyncio.Event) -> None:
    stop_event.set()
    task = runtime.sync_dispatcher
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as ex:  # pragma: no cover - defensive
        logger.warning(f"Sync dispatcher shutdown error: {ex}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    _warn_if_misconfigured(settings)

    runtime = build_runtime(settings)
    stop_event = start_dispatcher(runtime)
    yield
    await stop_dispatcher(runtime, stop_event)
    shutdown_runtime(runtime)

    # Stop the SSE broker before the pool it publishes through: on the Redis
    # backend close() cancels the pub/sub listener task, which would otherwise be
    # reading from a connection that has just been torn out from under it.
    await get_sse_broker().close()
    reset_sse_broker()
    if getattr(settings, "coordination_backend", "memory") == "redis":
        await close_redis()

    logger.info(f"Shutting down {settings.app_name}")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    install_exception_handlers(app)

    # No CORS middleware, deliberately: nothing in a browser may reach this
    # service. Every caller is another server on the internal network.

    app.include_router(health_router)
    app.include_router(market_router)
    app.include_router(assets_router)
    app.include_router(jobs_router)
    app.include_router(imports_router)

    return app


# Default app instance for `uvicorn kactus_data_plane.app:app`
app = create_app()
