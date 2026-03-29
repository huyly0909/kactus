"""Gold price API — Vietnamese domestic and global."""

from __future__ import annotations

from fastapi import Query, Request
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination
from kactus_data.schemas import SyncResult
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_fin.config import get_settings
from kactus_fin.gold.schema import (
    GoldGlobalItem,
    GoldVnItem,
    SyncGoldGlobalRequest,
    SyncGoldVnRequest,
)
from kactus_fin.gold.service import GoldService

router = KactusAPIRouter(prefix="/api/gold", tags=["gold"])


def _get_storage() -> DuckDBStorage:
    settings = get_settings()
    return DuckDBStorage(db_path=settings.db_path)


# ---------------------------------------------------------------------------
# Vietnamese gold
# ---------------------------------------------------------------------------


@router.get("/vn")
async def list_gold_vn(
    request: Request,
    brand: str | None = Query(None, description="Filter by brand: sjc, doji, pnj"),
) -> Pagination[GoldVnItem]:
    """List Vietnamese gold prices."""
    storage = _get_storage()
    items = GoldService.list_gold_vn(storage, brand=brand)
    return Pagination(total=len(items), items=items)


@router.post("/vn/sync")
async def sync_gold_vn(body: SyncGoldVnRequest, request: Request) -> SyncResult:
    """Sync Vietnamese gold prices for a brand."""
    storage = _get_storage()
    settings = get_settings()
    return GoldService.sync_gold_vn(
        storage,
        brand=body.brand,
        token=settings.vnappmob_token,
    )


# ---------------------------------------------------------------------------
# Global gold
# ---------------------------------------------------------------------------


@router.get("/global")
async def list_gold_global(
    request: Request,
    metal: str | None = Query(None, description="Filter by metal: XAU, XAG, XPT, XPD"),
) -> Pagination[GoldGlobalItem]:
    """List global precious metal prices."""
    storage = _get_storage()
    items = GoldService.list_gold_global(storage, metal=metal)
    return Pagination(total=len(items), items=items)


@router.post("/global/sync")
async def sync_gold_global(body: SyncGoldGlobalRequest, request: Request) -> SyncResult:
    """Sync global metal prices."""
    storage = _get_storage()
    settings = get_settings()
    return GoldService.sync_gold_global(
        storage,
        metal=body.metal,
        api_key=settings.metals_api_key,
    )
