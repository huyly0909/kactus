"""Every DuckDB table this package owns, in one place.

The OLAP side has no Alembic equivalent — tables are created lazily with
``CREATE TABLE IF NOT EXISTS`` on first write. This registry is what lets the
``schema`` CLI diff a live database against the current definitions and
rebuild the ones that have drifted.

Add new tables here as they are defined, or they will be invisible to the
drift check.

Timezone convention: ``event_dt`` is a reserved column name — on every table
that has it, it is the canonical UTC instant (naive UTC wall-clock) derived from
that row's native timestamp, and the single axis all time filtering / sync
compares against. Every other datetime/date column holds the source value
verbatim (Vietnam local, or a calendar day). See ``kactus_common.datetimes`` and
``kactus_data.util.time``.
"""

from kactus_common.database.duckdb.schema import Table
from kactus_data.sources.company.tables import COMPANY_TABLE
from kactus_data.sources.finance.tables import FINANCE_TABLE
from kactus_data.sources.gold.history_tables import GOLD_PRICE_HISTORY_TABLE
from kactus_data.sources.gold.portfolio_tables import (
    GOLD_PRICE_BOARD_TABLE,
    GOLD_PRICE_TICK_TABLE,
)
from kactus_data.sources.stock.portfolio_tables import (
    STOCK_DAILY_SNAPSHOT_TABLE,
    STOCK_EVENTS_TABLE,
    STOCK_FOREIGN_TRADE_TABLE,
    STOCK_NEWS_TABLE,
    STOCK_PRICE_BOARD_TABLE,
    STOCK_RATIOS_TABLE,
)
from kactus_data.sources.stock.tables import STOCK_LISTING_TABLE, STOCK_OHLCV_TABLE

ALL_TABLES: list[Table] = [
    COMPANY_TABLE,
    FINANCE_TABLE,
    GOLD_PRICE_BOARD_TABLE,
    GOLD_PRICE_HISTORY_TABLE,
    GOLD_PRICE_TICK_TABLE,
    STOCK_DAILY_SNAPSHOT_TABLE,
    STOCK_EVENTS_TABLE,
    STOCK_FOREIGN_TRADE_TABLE,
    STOCK_LISTING_TABLE,
    STOCK_NEWS_TABLE,
    STOCK_OHLCV_TABLE,
    STOCK_PRICE_BOARD_TABLE,
    STOCK_RATIOS_TABLE,
]

TABLES_BY_NAME: dict[str, Table] = {t.name: t for t in ALL_TABLES}

__all__ = ["ALL_TABLES", "TABLES_BY_NAME"]
