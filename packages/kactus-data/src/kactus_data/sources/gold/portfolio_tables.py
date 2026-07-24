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
