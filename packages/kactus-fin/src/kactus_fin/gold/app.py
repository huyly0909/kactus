"""Gold feature — KactusApp declaration."""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.gold.api import router

gold_app = KactusApp(
    name="gold",
    superuser_routes=[router],
)
