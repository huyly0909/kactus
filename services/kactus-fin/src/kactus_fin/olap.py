"""Process-wide OLAP (DuckDB) storage holder.

DuckDB is a single-file embedded database — opening the same file from several
``DuckDBStorage`` instances in one process invites lock contention, so the app
builds **one** storage in the lifespan and publishes it here.  Features that
only *read* the analytics tables (``market``) resolve it through
:func:`get_olap_storage` instead of constructing their own or reaching into the
portfolio runtime.
"""

from __future__ import annotations

from kactus_common.exceptions import InternalError
from kactus_data.storage.duckdb import DuckDBStorage

_storage: DuckDBStorage | None = None


def set_olap_storage(storage: DuckDBStorage | None) -> None:
    """Publish (or clear) the process-wide DuckDB storage."""
    global _storage
    _storage = storage


def get_olap_storage() -> DuckDBStorage:
    """Return the process-wide DuckDB storage, or raise if not initialised."""
    if _storage is None:
        raise InternalError("OLAP storage is not initialised")
    return _storage
