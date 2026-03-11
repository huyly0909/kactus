"""Company admin API — list, detail, sync."""

from __future__ import annotations

from fastapi import Request
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import Pagination
from kactus_data.schemas import SyncResult
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_fin.company.schema import CompanyDetail, CompanyItem, CompanySyncRequest
from kactus_fin.company.service import CompanyService
from kactus_fin.config import get_settings

router = KactusAPIRouter(prefix="/api/company", tags=["company"])


def _get_storage() -> DuckDBStorage:
    settings = get_settings()
    return DuckDBStorage(db_path=settings.db_path)


@router.get("")
async def list_companies(request: Request) -> Pagination[CompanyItem]:
    """List all companies from DuckDB."""
    storage = _get_storage()
    items = CompanyService.list_companies(storage)
    return Pagination(total=len(items), items=items)


@router.get("/{symbol}")
async def get_company(symbol: str, request: Request) -> CompanyDetail | None:
    """Get company detail with parsed overview JSON."""
    storage = _get_storage()
    return CompanyService.get_company(storage, symbol.upper())


@router.post("/sync")
async def sync_company(body: CompanySyncRequest, request: Request) -> SyncResult:
    """Sync company data for a symbol."""
    storage = _get_storage()
    return CompanyService.sync_company(storage, body.symbol.upper())
