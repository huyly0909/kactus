"""Stock feature — KactusApp declaration."""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.stock.api import router

stock_app = KactusApp(
    name="stock",
    superuser_routes=[router],
)
