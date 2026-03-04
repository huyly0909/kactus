"""DuckDB table definitions for financial data."""

from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table

FINANCE_TABLE = Table(
    name="stock_finance",
    columns=[
        Column(name="symbol", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="period", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="year", data_type=DataType.INT, is_primary_key=True, is_nullable=False),
        Column(name="quarter", data_type=DataType.INT, is_primary_key=True, is_nullable=False),
        Column(name="report_type", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="data_json", data_type=DataType.STRING),
        Column(name="source", data_type=DataType.STRING),
        Column(name="synced_at", data_type=DataType.TIMESTAMP),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)
