"""DuckDB table definitions for stock price data."""

from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table

STOCK_OHLCV_TABLE = Table(
    name="stock_ohlcv",
    columns=[
        Column(name="symbol", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="time", data_type=DataType.TIMESTAMP, is_primary_key=True, is_nullable=False),
        Column(name="interval", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="open", data_type=DataType.FLOAT),
        Column(name="high", data_type=DataType.FLOAT),
        Column(name="low", data_type=DataType.FLOAT),
        Column(name="close", data_type=DataType.FLOAT),
        Column(name="volume", data_type=DataType.FLOAT),
        Column(name="source", data_type=DataType.STRING),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

STOCK_LISTING_TABLE = Table(
    name="stock_listing",
    columns=[
        Column(name="symbol", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="organ_name", data_type=DataType.STRING),
        Column(name="source", data_type=DataType.STRING),
        Column(name="synced_at", data_type=DataType.TIMESTAMP),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)
