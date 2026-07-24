"""KactusApp & AppManager — feature-based application registration.

Each feature declares a ``KactusApp`` in its ``app.py`` and exposes it
via ``__init__.py``.  The main application imports each feature and
registers it with an ``AppManager``, which wires routers, middleware,
and permissions into FastAPI.

Usage (feature/app.py)::

    from kactus_common.app_registry import KactusApp
    from kactus_common.router import KactusAPIRouter

    router = KactusAPIRouter(prefix="/api/projects", tags=["projects"])

    project_app = KactusApp(
        name="project",
        session_routes=[router],
    )

Usage (main application)::

    from kactus_common.app_registry import AppManager
    from kactus_common.project import project_app

    app_manager = AppManager()
    app_manager.register(project_app)

    def create_app() -> FastAPI:
        app = FastAPI(...)
        app_manager.init_fastapi(app)
        return app
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI
from fastapi.routing import APIRouter

if TYPE_CHECKING:
    from kactus_common.authorization.const import Permission, PermissionAct
    from kactus_common.project.const import DefaultRole


@dataclass
class KactusApp:
    """Declares a feature's routes, permissions, and middleware.

    Attributes:
        name: Unique feature identifier (e.g. ``"project"``).
        public_routes: No authentication required.
        session_routes: Session cookie required — user set on ``request.state.user``.
        superuser_routes: Session + ``is_superuser`` required.
        permissions: Feature permission codes declared by this app.
        role_permissions: Default role → (permission, act) mapping.
        middlewares: ``(MiddlewareClass, options_dict)`` tuples.
        background_services: Callables to run as background tasks.
    """

    name: str

    # Routers
    public_routes: list[APIRouter] = field(default_factory=list)
    session_routes: list[APIRouter] = field(default_factory=list)
    superuser_routes: list[APIRouter] = field(default_factory=list)

    # Permissions
    permissions: list[Permission] = field(default_factory=list)
    role_permissions: dict[DefaultRole, list[tuple[Permission, PermissionAct]]] = field(
        default_factory=dict
    )

    # Middleware & background
    middlewares: list[tuple[Any, dict]] = field(default_factory=list)
    background_services: list[Callable] = field(default_factory=list)  # TODO: here


class AppManager:
    """Collects ``KactusApp`` instances and wires them into FastAPI."""

    def __init__(self) -> None:
        self.apps: dict[str, KactusApp] = {}
        self._auth_dependency: Callable | None = None
        self._superuser_dependency: Callable | None = None

    def register(self, app: KactusApp) -> None:
        """Register a KactusApp. Raises if name already taken."""
        if app.name in self.apps:
            raise ValueError(f"App '{app.name}' is already registered")
        self.apps[app.name] = app

    def set_auth_dependencies(
        self,
        *,
        session_dep: Callable,
        superuser_dep: Callable,
    ) -> None:
        """Set the auth dependencies that will be applied to routers.

        Args:
            session_dep: FastAPI dependency that authenticates the user,
                sets ``request.state.user`` and ``set_current_user_id()``.
            superuser_dep: FastAPI dependency that also requires ``is_superuser``.
        """
        self._auth_dependency = session_dep
        self._superuser_dependency = superuser_dep

    def init_fastapi(self, fastapi_app: FastAPI) -> None:
        """Wire all registered apps into the FastAPI instance."""
        self._init_routers(fastapi_app)
        self._init_middlewares(fastapi_app)
        self._init_authorization()

    def _init_routers(self, fastapi_app: FastAPI) -> None:
        """Register all app routers with appropriate auth dependencies."""
        for app in self.apps.values():
            # Public routes — no auth
            for router in app.public_routes:
                fastapi_app.include_router(router)

            # Session-protected routes
            if app.session_routes:
                if not self._auth_dependency:
                    raise RuntimeError(
                        f"App '{app.name}' has session_routes but no session "
                        f"auth dependency was set. Call set_auth_dependencies() first."
                    )
                for router in app.session_routes:
                    fastapi_app.include_router(
                        router,
                        dependencies=[Depends(self._auth_dependency)],
                    )

            # Superuser-protected routes
            if app.superuser_routes:
                if not self._superuser_dependency:
                    raise RuntimeError(
                        f"App '{app.name}' has superuser_routes but no superuser "
                        f"auth dependency was set. Call set_auth_dependencies() first."
                    )
                for router in app.superuser_routes:
                    fastapi_app.include_router(
                        router,
                        dependencies=[Depends(self._superuser_dependency)],
                    )

    def _init_middlewares(self, fastapi_app: FastAPI) -> None:
        """Register all app middlewares."""
        for app in self.apps.values():
            for middleware_class, options in app.middlewares:
                fastapi_app.add_middleware(middleware_class, **options)

    def _init_authorization(self) -> None:
        """Initialize CasbinService with aggregated role permissions."""
        role_permissions = self.get_role_permissions()
        if role_permissions:
            from kactus_common.authorization.casbin_service import init_casbin_service

            init_casbin_service(role_permissions)

    def get_all_permissions(self) -> list[Permission]:
        """Collect all permissions across registered apps."""
        perms: list[Permission] = []
        for app in self.apps.values():
            perms.extend(app.permissions)
        return perms

    def get_role_permissions(
        self,
    ) -> dict[DefaultRole, list[tuple[Permission, PermissionAct]]]:
        """Collect role-permission mappings across all apps."""
        result: dict[DefaultRole, list[tuple[Permission, PermissionAct]]] = {}
        for app in self.apps.values():
            for role, perm_tuples in app.role_permissions.items():
                result.setdefault(role, []).extend(perm_tuples)
        return result


def load_models(settings) -> None:
    """Import all ORM model modules from ``settings.INSTALLED_PACKAGES``.

    Each package listed in ``INSTALLED_PACKAGES`` must expose a
    ``MODELS: list[str]`` attribute in its ``__init__.py``.  Calling
    this ensures every ORM model is loaded into ``Base.metadata``
    before Alembic autogenerate runs.
    """
    import importlib

    for pkg_name in settings.INSTALLED_PACKAGES:
        pkg = importlib.import_module(pkg_name)
        for module_path in getattr(pkg, "MODELS", []):
            importlib.import_module(module_path)
