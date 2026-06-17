"""Process-wide portfolio runtime (db, providers, scheduler, symbol provider).

Populated by the app lifespan and read by the API endpoints (manual refresh,
market reads, admin status).  A module-level holder keeps endpoints decoupled
from how the runtime is constructed and lets tests inject a runtime directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.portfolio.const import AssetType
from kactus_common.portfolio.symbol_provider import SymbolProvider
from kactus_data.portfolio.provider import AssetProvider
from kactus_data.storage.duckdb import DuckDBStorage

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler


@dataclass
class PortfolioRuntime:
    db: DatabaseSessionManager
    providers: dict[AssetType, AssetProvider]
    storage: DuckDBStorage
    symbol_provider: SymbolProvider
    scheduler: "AsyncIOScheduler | None" = None
    _extra: dict = field(default_factory=dict)


_runtime: PortfolioRuntime | None = None


def set_runtime(runtime: PortfolioRuntime | None) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> PortfolioRuntime:
    if _runtime is None:
        from kactus_common.exceptions import InternalError

        raise InternalError("Portfolio runtime is not initialised")
    return _runtime
