"""Company data service — DuckDB queries and sync."""

from __future__ import annotations

import json
from datetime import date

from kactus_data.pipeline import SyncPipeline
from kactus_data.schemas import SyncResult
from kactus_data.sources.company import COMPANY_TABLE, VnstockCompanySource
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_fin.company.schema import CompanyDetail, CompanyItem


class CompanyService:
    """Query and sync company data from DuckDB."""

    @staticmethod
    def list_companies(storage: DuckDBStorage) -> list[CompanyItem]:
        """List all companies."""
        df = storage.query(
            "SELECT symbol, company_name, short_name, industry, exchange, "
            "market_cap, outstanding_shares, source, synced_at "
            "FROM stock_company ORDER BY symbol"
        )
        return [CompanyItem(**row) for row in df.to_dict("records")]

    @staticmethod
    def get_company(storage: DuckDBStorage, symbol: str) -> CompanyDetail | None:
        """Get company detail with parsed overview."""
        df = storage.query(
            f"SELECT * FROM stock_company WHERE symbol = '{symbol}'"
        )
        if df.empty:
            return None

        row = df.to_dict("records")[0]
        overview = None
        if row.get("overview_json"):
            try:
                overview = json.loads(row["overview_json"])
            except (json.JSONDecodeError, TypeError):
                overview = None

        return CompanyDetail(
            symbol=row["symbol"],
            company_name=row.get("company_name"),
            short_name=row.get("short_name"),
            industry=row.get("industry"),
            exchange=row.get("exchange"),
            market_cap=row.get("market_cap"),
            outstanding_shares=row.get("outstanding_shares"),
            source=row.get("source"),
            synced_at=str(row["synced_at"]) if row.get("synced_at") else None,
            overview=overview,
        )

    @staticmethod
    def sync_company(storage: DuckDBStorage, symbol: str) -> SyncResult:
        """Sync company data for a symbol."""
        source = VnstockCompanySource()
        pipeline = SyncPipeline(source=source, storage=storage)
        return pipeline.run(
            table=COMPANY_TABLE,
            code=symbol,
            start_date=date.today(),
            end_date=date.today(),
        )
