"""Market feature — KactusApp declaration for kactus-fin.

Read-only reference data: session auth is enough, no ownership or Casbin
permission checks apply.
"""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.market.api import router

market_app = KactusApp(
    name="market",
    session_routes=[router],
)
