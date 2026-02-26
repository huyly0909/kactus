"""Permission feature — KactusApp declaration."""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.permission.api import router

permission_app = KactusApp(
    name="permission",
    session_routes=[router],
)
