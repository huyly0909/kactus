"""Finance data service — DuckDB queries and sync."""

from __future__ import annotations

import json
from datetime import date

from kactus_data.pipeline import SyncPipeline
from kactus_data.schemas import SyncResult
from kactus_data.sources.finance import FINANCE_TABLE, VnstockFinanceSource
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_fin.finance.schema import FinanceDetail, FinanceItem


class FinanceService:
    """Query and sync finance data from DuckDB."""

    @staticmethod
    def list_finance(
        storage: DuckDBStorage,
        symbol: str | None = None,
        report_type: str | None = None,
    ) -> list[FinanceItem]:
        """List finance records with optional filters."""
        conditions: list[str] = []
        if symbol:
            conditions.append(f"symbol = '{symbol.upper()}'")
        if report_type:
            conditions.append(f"report_type = '{report_type}'")

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        df = storage.query(
            f"SELECT symbol, period, year, quarter, report_type, source, synced_at "
            f"FROM stock_finance{where} "
            f"ORDER BY symbol, year DESC, quarter DESC"
        )
        return [FinanceItem(**row) for row in df.to_dict("records")]

    @staticmethod
    def get_finance(storage: DuckDBStorage, symbol: str) -> list[FinanceDetail]:
        """Get all finance records for a symbol with parsed data."""
        df = storage.query(
            f"SELECT * FROM stock_finance WHERE symbol = '{symbol}' "
            f"ORDER BY year DESC, quarter DESC"
        )
        results: list[FinanceDetail] = []
        for row in df.to_dict("records"):
            data = None
            if row.get("data_json"):
                try:
                    data = json.loads(row["data_json"])
                except (json.JSONDecodeError, TypeError):
                    data = None

            results.append(
                FinanceDetail(
                    symbol=row["symbol"],
                    period=row["period"],
                    year=row["year"],
                    quarter=row["quarter"],
                    report_type=row["report_type"],
                    source=row.get("source"),
                    synced_at=str(row["synced_at"]) if row.get("synced_at") else None,
                    data=data,
                )
            )
        return results

    @staticmethod
    def sync_finance(
        storage: DuckDBStorage,
        symbol: str,
        report_type: str,
        period: str,
    ) -> SyncResult:
        """Sync finance data for a symbol."""
        source = VnstockFinanceSource()
        pipeline = SyncPipeline(source=source, storage=storage)
        return pipeline.run(
            table=FINANCE_TABLE,
            code=symbol,
            start_date=date.today(),
            end_date=date.today(),
        )
