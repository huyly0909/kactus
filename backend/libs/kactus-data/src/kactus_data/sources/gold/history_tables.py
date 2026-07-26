"""DuckDB table for historical gold price series (one row per code per day).

Unlike ``gold_price_board`` (latest snapshot, PK ``code``), this is a dated
series: PK ``(code, date)`` + UPSERT makes re-importing the same file
idempotent and lets a corrected file overwrite in place.

Series identity is the single ``code`` column — ``SJC``, ``XAU`` or
``PNJ:{location}:{gold_type}`` — with ``location``/``gold_type`` also kept as
their own nullable columns so nothing ever has to parse the composite code.
Domestic series carry ``buy_price``/``sell_price``; world gold (XAU) carries
OHLC. The unused side stays NULL — cheap in columnar storage, and one table
means one read path and one import path.
"""

from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table

GOLD_PRICE_HISTORY_TABLE = Table(
    name="gold_price_history",
    columns=[
        Column(
            name="code",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(
            name="date",
            data_type=DataType.DATE,
            is_primary_key=True,
            is_nullable=False,
        ),
        # Money → DECIMAL, same rationale as the board (VND ~1.4e8).
        Column(name="buy_price", data_type=DataType.DECIMAL),
        Column(name="sell_price", data_type=DataType.DECIMAL),
        Column(name="open", data_type=DataType.DECIMAL),
        Column(name="high", data_type=DataType.DECIMAL),
        Column(name="low", data_type=DataType.DECIMAL),
        Column(name="close", data_type=DataType.DECIMAL),
        Column(name="unit", data_type=DataType.STRING, is_nullable=False),
        Column(name="source", data_type=DataType.STRING),
        Column(name="location", data_type=DataType.STRING),
        Column(name="gold_type", data_type=DataType.STRING),
        Column(name="updated_at", data_type=DataType.TIMESTAMP),
        Column(name="imported_at", data_type=DataType.TIMESTAMP),
        # Canonical UTC instant derived from the native ``date`` (midnight in
        # Vietnam) — the unified UTC axis for cross-source time filtering.
        Column(name="event_dt", data_type=DataType.TIMESTAMP),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)
