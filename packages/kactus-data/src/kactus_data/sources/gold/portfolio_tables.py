"""DuckDB table for gold quote snapshots (portfolio watchlist)."""

from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table

GOLD_PRICE_BOARD_TABLE = Table(
    name="gold_price_board",
    columns=[
        Column(name="code", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="buy_price", data_type=DataType.FLOAT),
        Column(name="sell_price", data_type=DataType.FLOAT),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)
