"""Composable sync pipeline: source → transform → storage.

Designed to be called from Airflow DAGs, Celery tasks, or the CLI.
"""

from __future__ import annotations

import logging
import time
from datetime import date

import pandas as pd

from kactus_common.database.duckdb.consts import UpdateStrategy
from kactus_common.database.duckdb.schema import Table
from kactus_data.schemas import SyncResult
from kactus_data.sources.http import HttpDataSource
from kactus_data.storage.duckdb import DuckDBStorage

logger = logging.getLogger(__name__)


class SyncPipeline:
    """Fetch from a data source and store into DuckDB.

    Usage::

        from kactus_data.sources.gold import MihongGoldSource
        from kactus_data.storage.duckdb import DuckDBStorage
        from kactus_data.pipeline import SyncPipeline

        source = MihongGoldSource(xsrf_token="...")
        storage = DuckDBStorage(db_path="kactus.duckdb")
        pipeline = SyncPipeline(source, storage)

        result = pipeline.run(
            table=my_table,
            code="SJC",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )
    """

    def __init__(
        self,
        source: HttpDataSource,
        storage: DuckDBStorage,
    ) -> None:
        self.source = source
        self.storage = storage

    def run(
        self,
        table: Table,
        code: str,
        start_date: date,
        end_date: date,
        strategy: UpdateStrategy = UpdateStrategy.UPSERT,
        transform: callable | None = None,
    ) -> SyncResult:
        """Execute the full sync pipeline.

        Args:
            table: Target DuckDB table definition.
            code: Source-specific code (e.g. ``SJC``, ``BTC``).
            start_date: Start of the date range.
            end_date: End of the date range.
            strategy: How to merge data into the table.
            transform: Optional function ``(dict) -> pd.DataFrame``
                       to transform raw API data before storage.

        Returns:
            A :class:`SyncResult` summarising the pipeline run.
        """
        t0 = time.perf_counter()

        # 1. Fetch
        logger.info(
            "Syncing %s [%s] %s → %s",
            self.source.name,
            code,
            start_date,
            end_date,
        )
        response = self.source.sync(start_date, end_date, code)

        if not response.success:
            elapsed = (time.perf_counter() - t0) * 1000
            error_msg = str(response.error) if response.error else "Unknown error"
            logger.error("Sync failed for %s: %s", self.source.name, error_msg)
            return SyncResult(
                data_source=self.source.name,
                rows_fetched=0,
                rows_stored=0,
                table_name=table.name,
                duration_ms=elapsed,
                success=False,
                error=error_msg,
            )

        # 2. Transform
        raw_data = response.data or {}
        if transform is not None:
            df = transform(raw_data)
        else:
            # Default: try to create a DataFrame from the raw response data
            if isinstance(raw_data, list):
                df = pd.DataFrame(raw_data)
            elif isinstance(raw_data, dict) and raw_data:
                # Try common API patterns: data wrapped in a key
                for key in ("data", "results", "items", "prices", "records"):
                    if key in raw_data and isinstance(raw_data[key], list):
                        df = pd.DataFrame(raw_data[key])
                        break
                else:
                    df = pd.DataFrame([raw_data])
            else:
                df = pd.DataFrame()

        rows_fetched = len(df)

        # 3. Store
        if df.empty:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning("No rows to store for %s [%s]", self.source.name, code)
            return SyncResult(
                data_source=self.source.name,
                rows_fetched=0,
                rows_stored=0,
                table_name=table.name,
                duration_ms=elapsed,
                success=True,
            )

        rows_stored = self.storage.store(table, df, strategy)
        elapsed = (time.perf_counter() - t0) * 1000

        logger.info(
            "Pipeline complete: %d fetched, %d stored in %.0fms",
            rows_fetched,
            rows_stored,
            elapsed,
        )
        return SyncResult(
            data_source=self.source.name,
            rows_fetched=rows_fetched,
            rows_stored=rows_stored,
            table_name=table.name,
            duration_ms=elapsed,
            success=True,
        )
