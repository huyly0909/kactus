"""Company feature — KactusApp declaration."""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.company.api import router

company_app = KactusApp(
    name="company",
    superuser_routes=[router],
)
