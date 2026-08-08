"""Notification feature registration."""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.notification.api import router
from kactus_fin.notification.telegram_api import telegram_router
from kactus_fin.notification.zalo_pa_api import zalo_pa_router

notification_app = KactusApp(
    name="notification",
    # all routes require an authenticated user
    session_routes=[router, telegram_router, zalo_pa_router],
)
