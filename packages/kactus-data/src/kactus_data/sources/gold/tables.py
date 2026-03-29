"""DuckDB table definitions for gold price data."""

from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table

GOLD_VN_TABLE = Table(
    name="gold_vn",
    columns=[
        Column(name="brand", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="type", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="buy_price", data_type=DataType.FLOAT),
        Column(name="sell_price", data_type=DataType.FLOAT),
        Column(name="source", data_type=DataType.STRING),
        Column(name="synced_at", data_type=DataType.TIMESTAMP),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

GOLD_GLOBAL_TABLE = Table(
    name="gold_global",
    columns=[
        Column(name="metal", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="currency", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="price", data_type=DataType.FLOAT),
        Column(name="source", data_type=DataType.STRING),
        Column(name="synced_at", data_type=DataType.TIMESTAMP),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)
