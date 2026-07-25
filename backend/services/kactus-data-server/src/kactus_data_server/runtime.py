"""Process-wide data-plane runtime (db, DuckDB storage, providers, scheduler).

Populated by the app lifespan and read by the ``/internal`` endpoints. A
module-level holder keeps endpoints decoupled from how the runtime is
constructed and lets tests inject one directly.

``storage`` is the single DuckDB handle for this process, and this process is
the only one in the deployment holding one read-write. Everything that reads the
OLAP tables — the market service, the asset providers — goes through here; a
second handle on the same file would contend for the write lock even within one
process, which is why there is no separate holder module beside this one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.exceptions import InternalError
from kactus_common.portfolio.const import AssetType
from kactus_common.portfolio.symbol_provider import SymbolProvider
from kactus_data.portfolio.provider import AssetProvider
from kactus_data.storage.duckdb import DuckDBStorage

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler


@dataclass
class DataRuntime:
    db: DatabaseSessionManager
    providers: dict[AssetType, AssetProvider]
    storage: DuckDBStorage
    symbol_provider: SymbolProvider
    scheduler: "AsyncIOScheduler | None" = None
    _extra: dict = field(default_factory=dict)


_runtime: DataRuntime | None = None


def set_runtime(runtime: DataRuntime | None) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> DataRuntime:
    if _runtime is None:
        raise InternalError("Data runtime is not initialised")
    return _runtime
