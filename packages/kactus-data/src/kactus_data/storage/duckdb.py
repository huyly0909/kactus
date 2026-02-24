"""DuckDB storage adapter for ETL pipelines.

Wraps :class:`kactus_common.database.duckdb.client.DatabaseClient` with
ETL-friendly methods for storing, querying, and exporting data.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime

import pandas as pd

from kactus_common.database.duckdb.client import DatabaseClient
from kactus_common.database.duckdb.consts import UpdateStrategy
from kactus_common.database.duckdb.schema import Table

logger = logging.getLogger(__name__)


class DuckDBStorage:
    """High-level DuckDB storage for ETL data.

    Parameters:
        db_path: Path to the DuckDB database file.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._client = DatabaseClient(db_path)

    @property
    def client(self) -> DatabaseClient:
        """Access the underlying :class:`DatabaseClient`."""
        return self._client

    # ------------------------------------------------------------------
    # Store
    # ------------------------------------------------------------------

    def store(
        self,
        table: Table,
        data: pd.DataFrame,
        strategy: UpdateStrategy = UpdateStrategy.UPSERT,
    ) -> int:
        """Store a DataFrame into a DuckDB table.

        Creates the table if it doesn't exist, then writes data using
        the given update strategy.

        Returns:
            Number of rows written.
        """
        if data.empty:
            logger.info("No data to store for table %s", table.name)
            return 0

        # Ensure table exists
        if not self._client.table_exists(table.name):
            self._client.create_table(table.name, table.columns)
            logger.info("Created table %s", table.name)

        self._client.update_table(table, data)
        logger.info(
            "Stored %d rows in %s (strategy=%s)",
            len(data),
            table.name,
            strategy.value,
        )
        return len(data)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self, sql: str) -> pd.DataFrame:
        """Execute a SQL query and return results as a DataFrame."""
        result = self._client.execute(sql)
        if result and hasattr(result, "df"):
            return result.df()
        return pd.DataFrame()

    def list_tables(self) -> list[str]:
        """List all user tables in the database."""
        result = self._client.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main'"
        )
        if result:
            rows = result.fetchall()
            return [r[0] for r in rows]
        return []

    # ------------------------------------------------------------------
    # Export / Backup
    # ------------------------------------------------------------------

    def export_table(
        self,
        table_name: str,
        output_path: str,
        format: str = "parquet",
    ) -> str:
        """Export a single table to a file.

        Args:
            table_name: Name of the table to export.
            output_path: Directory to write the file into.
            format: Output format — ``parquet`` or ``csv``.

        Returns:
            Full path to the exported file.
        """
        os.makedirs(output_path, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{table_name}_{timestamp}.{format}"
        filepath = os.path.join(output_path, filename)

        if format == "parquet":
            sql = f"COPY {table_name} TO '{filepath}' (FORMAT PARQUET)"
        elif format == "csv":
            sql = f"COPY {table_name} TO '{filepath}' (FORMAT CSV, HEADER)"
        else:
            raise ValueError(f"Unsupported export format: {format}")

        self._client.execute(sql)
        logger.info("Exported %s → %s", table_name, filepath)
        return filepath

    def export_database(
        self,
        output_dir: str,
        format: str = "parquet",
    ) -> list[str]:
        """Export all tables to individual files.

        Returns:
            List of exported file paths.
        """
        tables = self.list_tables()
        if not tables:
            logger.warning("No tables found to export")
            return []

        paths: list[str] = []
        for table_name in tables:
            path = self.export_table(table_name, output_dir, format)
            paths.append(path)

        logger.info("Exported %d tables to %s", len(paths), output_dir)
        return paths

    def close(self) -> None:
        """No-op — connections are managed per-operation via context manager."""
        pass
