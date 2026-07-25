"""Admin feature — KactusApp declaration."""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.admin.api import router

admin_app = KactusApp(
    name="admin",
    superuser_routes=[router],
)
