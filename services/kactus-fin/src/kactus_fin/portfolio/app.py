"""Portfolio feature — KactusApp declaration for kactus-fin.

User-owned (not project-scoped), so routes are plain ``session_routes`` with
ownership enforced in the service layer; admin oversight is ``superuser_routes``.
"""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.portfolio.admin import router as admin_router
from kactus_fin.portfolio.api import assets_router, router

portfolio_app = KactusApp(
    name="portfolio",
    session_routes=[router, assets_router],
    superuser_routes=[admin_router],
)
