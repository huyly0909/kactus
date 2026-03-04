"""DuckDB table definitions for company data."""

from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table

COMPANY_TABLE = Table(
    name="stock_company",
    columns=[
        Column(name="symbol", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="company_name", data_type=DataType.STRING),
        Column(name="short_name", data_type=DataType.STRING),
        Column(name="industry", data_type=DataType.STRING),
        Column(name="exchange", data_type=DataType.STRING),
        Column(name="market_cap", data_type=DataType.FLOAT),
        Column(name="outstanding_shares", data_type=DataType.FLOAT),
        Column(name="overview_json", data_type=DataType.STRING),
        Column(name="source", data_type=DataType.STRING),
        Column(name="synced_at", data_type=DataType.TIMESTAMP),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)
