"""Notification feature registration."""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.notification.api import router

notification_app = KactusApp(
    name="notification",
    session_routes=[router],  # all routes require an authenticated user
)
