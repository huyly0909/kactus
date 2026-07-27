"""DuckDB table for gold quote snapshots (portfolio watchlist)."""

from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table

# Price unit markers — the board mixes domestic and world gold, which are quoted
# in different units, so every row records which one it is.
UNIT_VND_PER_LUONG = "VND/luong"
UNIT_USD_PER_OZ = "USD/oz"

GOLD_PRICE_BOARD_TABLE = Table(
    name="gold_price_board",
    columns=[
        Column(
            name="code",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        # Money → DECIMAL. Domestic gold is ~1.4e8 VND/lượng, which binary floats
        # cannot represent exactly.
        Column(name="buy_price", data_type=DataType.DECIMAL),
        Column(name="sell_price", data_type=DataType.DECIMAL),
        Column(name="unit", data_type=DataType.STRING),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

# Intraday tick log: every sync-now (and every scheduled crawl) appends one row
# per (source, code), stamped with the crawl instant. Where ``gold_price_board``
# keeps only the latest snapshot, this keeps the whole trail — so the UI can show
# how many times a price moved within a day. PK ``(source, code, crawled_at)``
# with UPSERT only defuses an exact-timestamp collision (near-impossible at
# microsecond precision); it never overwrites a distinct tick.
#
# ``crawled_at`` is written directly as UTC (``utcnow_naive()``), so — like the
# board and other audit-only tables — this table has **no** ``event_dt``.
GOLD_PRICE_TICK_TABLE = Table(
    name="gold_price_tick",
    columns=[
        Column(
            name="code",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(
            name="source",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(
            name="crawled_at",
            data_type=DataType.TIMESTAMP,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(name="buy_price", data_type=DataType.DECIMAL),
        Column(name="sell_price", data_type=DataType.DECIMAL),
        Column(name="unit", data_type=DataType.STRING),
        Column(name="raw_json", data_type=DataType.STRING),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)
