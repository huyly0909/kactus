"""DuckDB table for historical gold price series (one row per source+code+day).

Unlike ``gold_price_board`` (latest snapshot, PK ``code``), this is a dated
series: PK ``(source, code, date)`` + UPSERT makes re-importing / re-backfilling
the same day idempotent and lets a corrected value overwrite in place.

``source`` is part of the identity because the same ``code`` can come from more
than one feed and they must coexist rather than clobber each other: SJC-999 (the
issuer's official ring) and Mihong-999 (a dealer quote) are different series of
the same code. Series identity is therefore ``(source, code)`` — with
``location``/``gold_type`` kept as their own nullable columns so nothing ever has
to parse a composite code. Domestic series carry ``buy_price``/``sell_price``;
world gold (XAU) carries OHLC. The unused side stays NULL — cheap in columnar
storage, and one table means one read path and one import path.
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
        # Part of the PK: (source, code) is the series identity — SJC-999 and
        # Mihong-999 are distinct series of the same code.
        Column(
            name="source",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
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
