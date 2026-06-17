"""DuckDB (OLAP) table definitions for portfolio stock crawls.

Each table keeps a small set of *curated* columns for fast display plus a
``raw_json`` catch-all holding the full source row.  This makes the schema
resilient to vnstock's column variance across sources (KBS vs VCI ``price_board``
columns differ) — new fields land in ``raw_json`` without a migration.
"""

from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table

# Latest quote snapshot per symbol (watchlist board). UPSERT on symbol → keep
# only the freshest row.
STOCK_PRICE_BOARD_TABLE = Table(
    name="stock_price_board",
    columns=[
        Column(name="symbol", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="match_price", data_type=DataType.FLOAT),
        Column(name="ref_price", data_type=DataType.FLOAT),
        Column(name="ceiling", data_type=DataType.FLOAT),
        Column(name="floor", data_type=DataType.FLOAT),
        Column(name="accumulated_volume", data_type=DataType.FLOAT),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

STOCK_NEWS_TABLE = Table(
    name="stock_news",
    columns=[
        Column(name="symbol", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="news_id", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="title", data_type=DataType.STRING),
        Column(name="published_at", data_type=DataType.STRING),
        Column(name="url", data_type=DataType.STRING),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

STOCK_FOREIGN_TRADE_TABLE = Table(
    name="stock_foreign_trade",
    columns=[
        Column(name="symbol", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="trade_date", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="buy_value", data_type=DataType.FLOAT),
        Column(name="sell_value", data_type=DataType.FLOAT),
        Column(name="net_value", data_type=DataType.FLOAT),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

STOCK_RATIOS_TABLE = Table(
    name="stock_ratios",
    columns=[
        Column(name="symbol", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="period", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

STOCK_EVENTS_TABLE = Table(
    name="stock_events",
    columns=[
        Column(name="symbol", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="event_id", data_type=DataType.STRING, is_primary_key=True, is_nullable=False),
        Column(name="title", data_type=DataType.STRING),
        Column(name="event_date", data_type=DataType.STRING),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)
