"""DuckDB table for gold quote snapshots (portfolio watchlist)."""

from kactus_common.database.duckdb.consts import DataType, UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table

# Price unit markers — the board mixes domestic and world gold, which are quoted
# in different units, so every row records which one it is.
UNIT_VND_PER_LUONG = "VND/luong"
UNIT_USD_PER_OZ = "USD/oz"

#: Codes mihong quotes as a **series of its own**, not merely as an SJC fallback.
#: SJC publishes 999 too (the ring), and the two are different products of the
#: same code — so the hourly crawl fetches both and the board keeps both.
MIHONG_BOARD_CODES = frozenset({"999"})

#: Board sources ranked by authority, for the one place that must collapse a
#: code to a single quote (``GoldAssetProvider.read`` — a portfolio holding of
#: "999" is one position and cannot show two prices). SJC issues the domestic
#: reference price; yahoo is the only XAU feed; mihong is a dealer quote.
BOARD_SOURCE_PRIORITY = ("sjc", "yahoo", "mihong")

# Series identity is ``(code, source)``, same as ``gold_price_history`` — the
# same code can come from more than one feed and they must coexist rather than
# clobber each other: SJC-999 (the issuer's official ring) and Mihong-999 (a
# dealer quote) are different series that happen to share a code. With PK
# ``code`` alone the upsert deleted by code, so whichever source crawled last
# silently owned the row — and mihong, being the fallback, always lost.
#
# ``crawled_at`` is written directly as UTC (``utcnow_naive()``), so this
# snapshot table has **no** ``event_dt``.
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
        # Part of the PK. Kept in place rather than moved up beside ``code``:
        # inserts are positional (``INSERT … SELECT *``), so reordering columns
        # misaligns values on every database that already has the table.
        Column(
            name="source",
            data_type=DataType.STRING,
            is_primary_key=True,
            is_nullable=False,
        ),
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
