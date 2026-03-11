"""Finance feature — KactusApp declaration."""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.finance.api import router

finance_app = KactusApp(
    name="finance",
    superuser_routes=[router],
)
