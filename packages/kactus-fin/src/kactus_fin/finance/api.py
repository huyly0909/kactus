"""Finance admin API — list, detail, sync."""

from __future__ import annotations

from fastapi import Request
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination
from kactus_data.schemas import SyncResult
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_fin.config import get_settings
from kactus_fin.finance.schema import FinanceDetail, FinanceItem, FinanceSyncRequest
from kactus_fin.finance.service import FinanceService

router = KactusAPIRouter(prefix="/api/finance", tags=["finance"])


def _get_storage() -> DuckDBStorage:
    settings = get_settings()
    return DuckDBStorage(db_path=settings.db_path)


@router.get("")
async def list_finance(
    request: Request,
    symbol: str | None = None,
    report_type: str | None = None,
) -> Pagination[FinanceItem]:
    """List finance records with optional filters."""
    storage = _get_storage()
    items = FinanceService.list_finance(storage, symbol=symbol, report_type=report_type)
    return Pagination(total=len(items), items=items)


@router.get("/{symbol}")
async def get_finance(symbol: str, request: Request) -> list[FinanceDetail]:
    """Get all finance records for a symbol with parsed data."""
    storage = _get_storage()
    return FinanceService.get_finance(storage, symbol.upper())


@router.post("/sync")
async def sync_finance(body: FinanceSyncRequest, request: Request) -> SyncResult:
    """Sync finance data for a symbol."""
    storage = _get_storage()
    return FinanceService.sync_finance(storage, body.symbol.upper(), body.report_type, body.period)
