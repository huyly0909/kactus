from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from kactus_common.app_registry import AppManager
from kactus_common.database.oltp.session import get_db
from kactus_common.exceptions import PermissionDeniedError, install_exception_handlers
from kactus_data.jobs.scheduler import build_scheduler
from kactus_data.portfolio.provider import build_providers
from kactus_data.sources.stock.auth import init_vnstock_auth
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_fin.admin.app import admin_app
from kactus_fin.api.health import router as health_router
from kactus_fin.auth.app import auth_app
from kactus_fin.config import get_settings
from kactus_fin.dependencies import get_auth
from kactus_fin.permission.app import permission_app
from kactus_fin.portfolio.app import portfolio_app
from kactus_fin.portfolio.runtime import PortfolioRuntime, set_runtime
from kactus_fin.portfolio.sse import register_sse_handler
from kactus_fin.portfolio.symbol_provider import FinSymbolProvider
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
app_manager.set_auth_dependencies(
    session_dep=_session_auth,
    superuser_dep=_superuser_auth,
)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def _build_portfolio_runtime(settings) -> PortfolioRuntime:
    """Authenticate vnstock, build providers, register SSE, start scheduler."""
    init_vnstock_auth()

    db = get_db()
    storage = DuckDBStorage(settings.db_path)
    providers = build_providers(
        storage,
        data_source=settings.data_source,
        mihong_token=getattr(settings, "mihong_xsrf_token", ""),
    )
    symbol_provider = FinSymbolProvider(db)

    # MUST precede scheduler start (blinker KeyError otherwise).
    register_sse_handler()

    scheduler = None
    if getattr(settings, "enable_portfolio_scheduler", True):
        scheduler = build_scheduler(
            db=db,
            providers=providers,
            symbol_provider=symbol_provider,
            storage=storage,
            data_source=settings.data_source,
        )
        try:
            scheduler.start()
        except Exception as ex:  # pragma: no cover - defensive
            logger.warning(f"Portfolio scheduler failed to start: {ex}")
            scheduler = None

    runtime = PortfolioRuntime(
        db=db,
        providers=providers,
        storage=storage,
        symbol_provider=symbol_provider,
        scheduler=scheduler,
    )
    set_runtime(runtime)
    logger.info(
        f"Portfolio runtime initialised (scheduler={'on' if scheduler else 'off'})"
    )
    return runtime


def _shutdown_portfolio_runtime(runtime: PortfolioRuntime | None) -> None:
    if runtime is not None and runtime.scheduler is not None:
        try:
            runtime.scheduler.shutdown(wait=False)
        except Exception:  # pragma: no cover - defensive
            pass
    set_runtime(None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — also boots the portfolio crawler + SSE.

    Order is load-bearing:
      1. authenticate vnstock (paid tier, else guest),
      2. register the SSE handler BEFORE the scheduler starts (blinker raises
         ``KeyError`` on a foreground dispatch with no handler registered yet),
      3. build + start the in-process scheduler and publish the runtime.
    """
    from loguru import logger

    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    runtime = _build_portfolio_runtime(settings)
    yield
    _shutdown_portfolio_runtime(runtime)
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
