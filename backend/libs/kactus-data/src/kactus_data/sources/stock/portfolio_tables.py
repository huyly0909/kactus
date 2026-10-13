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
        Column(
            name="symbol",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(name="match_price", data_type=DataType.DECIMAL),
        Column(name="ref_price", data_type=DataType.DECIMAL),
        Column(name="ceiling", data_type=DataType.DECIMAL),
        Column(name="floor", data_type=DataType.DECIMAL),
        # See stock_ohlcv.volume — FLOAT loses whole shares above ~16.7M.
        Column(name="accumulated_volume", data_type=DataType.DOUBLE),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

STOCK_NEWS_TABLE = Table(
    name="stock_news",
    columns=[
        Column(
            name="symbol",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(
            name="news_id",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(name="title", data_type=DataType.STRING),
        Column(name="published_at", data_type=DataType.STRING),
        Column(name="url", data_type=DataType.STRING),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
        # Canonical UTC instant derived from the native ``published_at`` (Vietnam
        # local) — the unified UTC axis for time filtering. Kept last so an
        # ``ALTER TABLE ADD COLUMN`` on an existing DB matches this order.
        Column(name="event_dt", data_type=DataType.TIMESTAMP),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

STOCK_FOREIGN_TRADE_TABLE = Table(
    name="stock_foreign_trade",
    columns=[
        Column(
            name="symbol",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(
            name="trade_date",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(name="buy_value", data_type=DataType.DECIMAL),
        Column(name="sell_value", data_type=DataType.DECIMAL),
        Column(name="net_value", data_type=DataType.DECIMAL),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
        # Canonical UTC instant derived from the native ``trade_date`` (Vietnam
        # trading day) — the unified UTC axis for time filtering. Kept last so an
        # ``ALTER TABLE ADD COLUMN`` on an existing DB matches this order.
        Column(name="event_dt", data_type=DataType.TIMESTAMP),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

STOCK_RATIOS_TABLE = Table(
    name="stock_ratios",
    columns=[
        Column(
            name="symbol",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(
            name="period",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

# End-of-session snapshot, one row per (symbol, trading day).
#
# This is how the foreign-flow series gets built at all. ``Trading.foreign_trade``
# raises NotImplementedError on VCI (only the now-dead TCBS ever served it), but
# the price board already carries the same figures for the *current* session —
# verified against the exchange for FPT 2026-07-27: buy 52.67bn / sell 52.55bn,
# matching to the last decimal. Persisting the board after close therefore
# reconstructs what the API cannot give us.
#
# The cost is that it is FORWARD-ONLY: history begins the day snapshots begin and
# there is no way to backfill it. That is also why this is a separate table from
# ``stock_price_board`` — that one is UPSERT-on-symbol and keeps only the latest
# row, so each session would overwrite the last.
STOCK_DAILY_SNAPSHOT_TABLE = Table(
    name="stock_daily_snapshot",
    columns=[
        Column(
            name="symbol",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        # The session the board describes, taken from its own
        # ``listing_trading_date`` rather than the wall clock — a snapshot run
        # after midnight VN would otherwise be filed under the wrong day.
        Column(
            name="trade_date",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(name="close_price", data_type=DataType.DECIMAL),
        Column(name="ref_price", data_type=DataType.DECIMAL),
        Column(name="change", data_type=DataType.DECIMAL),
        Column(name="change_pct", data_type=DataType.FLOAT),
        # Counts/volumes stay DOUBLE; FLOAT loses whole shares above ~16.7M.
        Column(name="volume", data_type=DataType.DOUBLE),
        # Absolute VND. The board publishes this in *millions* — converted on
        # ingest so every money column in this table shares one unit.
        Column(name="value_vnd", data_type=DataType.DECIMAL),
        Column(name="remain_bid", data_type=DataType.DOUBLE),
        Column(name="remain_ask", data_type=DataType.DOUBLE),
        Column(name="avg_buy_size", data_type=DataType.DOUBLE),
        Column(name="avg_sell_size", data_type=DataType.DOUBLE),
        Column(name="foreign_buy_volume", data_type=DataType.DOUBLE),
        Column(name="foreign_sell_volume", data_type=DataType.DOUBLE),
        Column(name="foreign_buy_value", data_type=DataType.DECIMAL),
        Column(name="foreign_sell_value", data_type=DataType.DECIMAL),
        Column(name="foreign_net_value", data_type=DataType.DECIMAL),
        Column(name="current_room", data_type=DataType.DOUBLE),
        Column(name="total_room", data_type=DataType.DOUBLE),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
        # Canonical UTC instant derived from the native ``trade_date`` (Vietnam
        # trading day) — the unified UTC axis for time filtering. Kept last so an
        # ``ALTER TABLE ADD COLUMN`` on an existing DB matches this order.
        Column(name="event_dt", data_type=DataType.TIMESTAMP),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)

STOCK_EVENTS_TABLE = Table(
    name="stock_events",
    columns=[
        Column(
            name="symbol",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(
            name="event_id",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
        Column(name="title", data_type=DataType.STRING),
        Column(name="event_date", data_type=DataType.STRING),
        Column(name="source", data_type=DataType.STRING),
        Column(name="crawled_at", data_type=DataType.TIMESTAMP),
        Column(name="raw_json", data_type=DataType.STRING),
        # Canonical UTC instant derived from the native ``event_date`` (Vietnam
        # local) — the unified UTC axis for time filtering. Kept last so an
        # ``ALTER TABLE ADD COLUMN`` on an existing DB matches this order.
        Column(name="event_dt", data_type=DataType.TIMESTAMP),
    ],
    update_strategy=UpdateStrategy.UPSERT,
)
