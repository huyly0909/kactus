"""Stock admin API — listing, OHLCV, sync."""

from __future__ import annotations

from datetime import date

from fastapi import Request
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination
from kactus_data.schemas import SyncResult
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_fin.config import get_settings
from kactus_fin.stock.schema import OhlcvItem, StockListingItem, SyncOhlcvRequest
from kactus_fin.stock.service import StockService

router = KactusAPIRouter(prefix="/api/stock", tags=["stock"])


def _get_storage() -> DuckDBStorage:
    settings = get_settings()
    return DuckDBStorage(db_path=settings.db_path)


@router.get("")
async def list_stocks(request: Request) -> Pagination[StockListingItem]:
    """List all stock listings."""
    storage = _get_storage()
    items = StockService.list_stocks(storage)
    return Pagination(total=len(items), items=items)


@router.get("/{symbol}/ohlcv")
async def get_ohlcv(symbol: str, request: Request) -> list[OhlcvItem]:
    """Get OHLCV data for a symbol."""
    storage = _get_storage()
    return StockService.get_ohlcv(storage, symbol.upper())


@router.post("/sync-listing")
async def sync_listing(request: Request) -> SyncResult:
    """Sync all stock listings."""
    storage = _get_storage()
    return StockService.sync_listing(storage)


@router.post("/sync-ohlcv")
async def sync_ohlcv(body: SyncOhlcvRequest, request: Request) -> SyncResult:
    """Sync OHLCV data for a symbol and date range."""
    storage = _get_storage()
    return StockService.sync_ohlcv(
        storage,
        symbol=body.symbol.upper(),
        start_date=date.fromisoformat(body.start_date),
        end_date=date.fromisoformat(body.end_date),
    )
