import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from kactus_common.app_registry import AppManager
from kactus_common.exceptions import PermissionDeniedError, install_exception_handlers
from kactus_common.redis.client import close_redis
from kactus_common.sse.broker import get_sse_broker, reset_sse_broker
from kactus_fin.action.app import action_app
from kactus_fin.admin.app import admin_app
from kactus_fin.api.health import router as health_router
from kactus_fin.auth.app import auth_app
from kactus_fin.config import get_settings
from kactus_fin.data_client import close_client
from kactus_fin.dependencies import get_auth
from kactus_fin.market.app import market_app
from kactus_fin.notification.app import notification_app
from kactus_fin.notification.consumer import start_consumer, stop_consumer
from kactus_fin.permission.app import permission_app
from kactus_fin.portfolio.app import portfolio_app
from kactus_fin.project.app import project_app
from loguru import logger

# ---------------------------------------------------------------------------
# Auth dependencies (set ContextVar + request.state.user)
# ---------------------------------------------------------------------------


async def _session_auth(request: Request) -> None:
    """Authenticate via session cookie, set request.state.user + ContextVar."""
    auth = get_auth()
    await auth.get_current_user(request)


async def _superuser_auth(request: Request) -> None:
    """Authenticate + require is_superuser."""
    auth = get_auth()
    user = await auth.get_current_user(request)
    if not user.is_superuser:
        raise PermissionDeniedError("Superuser access required")


# ---------------------------------------------------------------------------
# App Manager — register features
# ---------------------------------------------------------------------------

app_manager = AppManager()
app_manager.register(auth_app)
app_manager.register(project_app)
app_manager.register(permission_app)
app_manager.register(admin_app)
app_manager.register(portfolio_app)
app_manager.register(notification_app)
app_manager.register(market_app)
app_manager.register(action_app)
app_manager.set_auth_dependencies(
    session_dep=_session_auth,
    superuser_dep=_superuser_auth,
)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


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


def _warn_if_multi_worker(settings) -> None:
    """Warn when several workers would share no cross-process state.

    kactus-fin is free to scale out now — the scheduler and the DuckDB handle
    that used to pin it to one process live in the data plane. What is still
    per-process on the ``memory`` backend is the SSE broker and the Zalo QR
    session store, so that combination is the one remaining way a multi-worker
    deployment breaks.

    A warning, not a refusal: the failure it describes is partial (some clients
    miss some events), and an operator who has read this and decided otherwise
    should not have the process refuse to boot.
    """
    workers = _detected_worker_count()
    if workers is None or workers <= 1:
        return

    if getattr(settings, "coordination_backend", "memory") != "redis":
        logger.warning(
            f"kactus-fin looks like it is running with {workers} workers while "
            "KACTUS_COORDINATION_BACKEND=memory. The SSE broker and the Zalo PA "
            "QR session store are per-process: expect SSE to reach only some "
            "clients and QR logins to fail when the 5 steps land on different "
            "workers. Set KACTUS_COORDINATION_BACKEND=redis."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan.

    Short by design. Everything that used to be built here — vnstock auth, the
    DuckDB handle, the asset providers, the crawl scheduler — moved to
    kactus-data-server. This process owns no long-lived resource beyond its
    connection pools, which is what lets it run at more than one worker.
    """
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    _warn_if_multi_worker(settings)

    # The notification queue consumer is the one long-lived task here, and it is
    # deliberately per-worker: a Redis consumer group distributes entries across
    # its members, so N workers means N senders, not N copies of every message.
    # Skipped on the memory backend, where there is no Redis and the API sends
    # inline instead (see kactus_fin/notification/api.py::_queue_enabled).
    consumer_running = getattr(
        settings, "coordination_backend", "memory"
    ) == "redis" and getattr(settings, "notification_queue_enabled", True)
    if consumer_running:
        await start_consumer()

    yield

    if consumer_running:
        await stop_consumer()

    # Stop the SSE broker before the pool it publishes through: on the Redis
    # backend close() cancels the pub/sub listener task, which would otherwise be
    # reading from a connection that has just been torn out from under it.
    await get_sse_broker().close()
    reset_sse_broker()
    await close_client()
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

    # Exception handlers
    install_exception_handlers(app)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check (no feature, standalone)
    app.include_router(health_router)

    # Wire all feature apps (routes, middleware, background)
    app_manager.init_fastapi(app)

    return app


# Default app instance for `uvicorn kactus_fin.app:app`
app = create_app()
