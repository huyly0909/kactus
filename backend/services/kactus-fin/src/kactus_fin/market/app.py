"""Market feature — KactusApp declaration for kactus-fin.

Read-only reference data: session auth is enough, no ownership or Casbin
permission checks apply. The one write — importing historical gold CSVs — is
superuser-only, same pattern as portfolio admin oversight.
"""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.market.admin_api import router as admin_router
from kactus_fin.market.api import router

market_app = KactusApp(
    name="market",
    session_routes=[router],
    superuser_routes=[admin_router],
)
