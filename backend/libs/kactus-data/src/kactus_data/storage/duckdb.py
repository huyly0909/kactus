"""DuckDB storage adapter for ETL pipelines.

Wraps :class:`kactus_common.database.duckdb.client.DatabaseClient` with
ETL-friendly methods for storing, querying, and exporting data.
"""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
from kactus_common.database.duckdb.client import DatabaseClient
from kactus_common.database.duckdb.consts import UpdateStrategy
from kactus_common.database.duckdb.schema import Table
from loguru import logger


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
    # Schema
    # ------------------------------------------------------------------

    def schema_drift(self, table: Table) -> list[str]:
        """Describe how the on-disk table differs from its definition.

        Tables are created with ``CREATE TABLE IF NOT EXISTS``, so a definition
        change (a new column, FLOAT → DECIMAL) never reaches a database that
        already has the table. Since the INSERT is positional, drift is not
        cosmetic: it misaligns values or fails outright. Returns an empty list
        when the table matches or does not exist yet.

        Columns **and primary keys** are compared; nullability deliberately is
        not — every table predating the current definitions would light up and
        turn ``schema check`` into noise.
        """
        if not self._client.table_exists(table.name):
            return []

        actual = self._client.get_column_types(table.name)
        expected = {c.name: c.sql_type for c in table.columns}
        # DESCRIBE reports canonical names (VARCHAR, INTEGER); our definitions
        # use aliases (STRING, INT). Normalise before comparing.
        canonical = self._client.canonical_types(list(expected.values()))
        drift: list[str] = []

        for name, want in expected.items():
            have = actual.get(name)
            if have is None:
                drift.append(f"missing column {name} ({want})")
            elif have != canonical[want]:
                drift.append(f"{name}: {have} → {want}")

        drift.extend(
            f"extra column {n} ({t})" for n, t in actual.items() if n not in expected
        )

        # A PK change is invisible in the column diff (same names, same types)
        # yet breaks the UPSERT: the DELETE is built from the *definition*'s key
        # while the on-disk constraint is the old one. Compare as sets —
        # DESCRIBE lists columns in table order, not key order.
        info = self._client.get_table_info(table.name)
        actual_pk = {
            name for name, key in zip(info["column_name"], info["key"]) if key == "PRI"
        }
        expected_pk = table.get_primary_key_columns()
        if actual_pk != set(expected_pk):
            drift.append(
                f"primary key ({', '.join(sorted(actual_pk)) or 'none'}) → "
                f"({', '.join(expected_pk) or 'none'})"
            )
        return drift

    def recreate_table(self, table: Table) -> None:
        """Drop the table and rebuild it from its definition. Destructive."""
        self._client.drop_table(table.name)
        self._client.create_table(table.name, table.columns)
        logger.warning("Recreated table {} — previous rows discarded", table.name)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(self, sql: str, params: list | tuple | None = None) -> pd.DataFrame:
        """Execute a SQL query and return results as a DataFrame.

        ``params`` binds DuckDB positional placeholders (``?``); use it for any
        caller-supplied value instead of interpolating into *sql*.
        """
        result = self._client.execute(sql, params)
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
