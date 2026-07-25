"""Auth feature — KactusApp declaration."""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.auth.api import router, session_router

auth_app = KactusApp(
    name="auth",
    public_routes=[router],
    session_routes=[session_router],
)
