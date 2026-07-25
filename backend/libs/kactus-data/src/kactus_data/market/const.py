"""DuckDB table names the market read models query.

Derived from the ``Table`` definitions that the ETL writes rather than repeated
as string literals. In its previous home (kactus-fin) this was a hand-kept copy
of the same seven names: renaming a table there would have left the reader
querying a table that no longer exists, and nothing would have failed until a
request came in. Now the two cannot disagree.
"""

from __future__ import annotations

from kactus_data.sources.company.tables import COMPANY_TABLE
from kactus_data.sources.finance.tables import FINANCE_TABLE
from kactus_data.sources.gold.portfolio_tables import GOLD_PRICE_BOARD_TABLE
from kactus_data.sources.stock.portfolio_tables import (
    STOCK_NEWS_TABLE as _STOCK_NEWS_TABLE,
)
from kactus_data.sources.stock.portfolio_tables import (
    STOCK_PRICE_BOARD_TABLE as _STOCK_PRICE_BOARD_TABLE,
)
from kactus_data.sources.stock.tables import STOCK_LISTING_TABLE as _STOCK_LISTING_TABLE
from kactus_data.sources.stock.tables import STOCK_OHLCV_TABLE as _STOCK_OHLCV_TABLE

GOLD_BOARD_TABLE = GOLD_PRICE_BOARD_TABLE.name
STOCK_LISTING_TABLE = _STOCK_LISTING_TABLE.name
STOCK_COMPANY_TABLE = COMPANY_TABLE.name
STOCK_PRICE_BOARD_TABLE = _STOCK_PRICE_BOARD_TABLE.name
STOCK_OHLCV_TABLE = _STOCK_OHLCV_TABLE.name
STOCK_NEWS_TABLE = _STOCK_NEWS_TABLE.name
STOCK_FINANCE_TABLE = FINANCE_TABLE.name
