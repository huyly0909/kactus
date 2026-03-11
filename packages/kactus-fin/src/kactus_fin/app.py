from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from kactus_common.app_registry import AppManager
from kactus_common.exceptions import PermissionDeniedError, install_exception_handlers
from kactus_fin.admin.app import admin_app
from kactus_fin.api.health import router as health_router
from kactus_fin.auth.app import auth_app
from kactus_fin.company.app import company_app
from kactus_fin.config import get_settings
from kactus_fin.dependencies import get_auth
from kactus_fin.finance.app import finance_app
from kactus_fin.permission.app import permission_app
from kactus_fin.project.app import project_app
from kactus_fin.stock.app import stock_app

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
app_manager.register(company_app)
app_manager.register(finance_app)
app_manager.register(stock_app)
app_manager.set_auth_dependencies(
    session_dep=_session_auth,
    superuser_dep=_superuser_auth,
)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    settings = get_settings()
    print(f"Starting {settings.app_name} v{settings.app_version}")
    yield
    print(f"Shutting down {settings.app_name}")


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
