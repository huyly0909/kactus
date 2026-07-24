"""Market feature constants.

Values mirror what the ETL writes into DuckDB (see
``kactus_data.sources.finance.vnstock.REPORT_TYPES`` and
``VnstockOHLCVSource.interval``), so the API rejects anything that could never
match a stored row instead of silently returning an empty list.
"""

from __future__ import annotations

from enum import StrEnum

# DuckDB tables owned by the ETL and read (never written) by this feature.
GOLD_BOARD_TABLE = "gold_price_board"
STOCK_LISTING_TABLE = "stock_listing"
STOCK_COMPANY_TABLE = "stock_company"
STOCK_PRICE_BOARD_TABLE = "stock_price_board"
STOCK_OHLCV_TABLE = "stock_ohlcv"
STOCK_NEWS_TABLE = "stock_news"
STOCK_FINANCE_TABLE = "stock_finance"

# Read caps — the OLAP tables are unbounded, the API is not.
MAX_LIMIT = 2000
DEFAULT_OHLCV_LIMIT = 500
DEFAULT_LIST_LIMIT = 50
DEFAULT_NEWS_LIMIT = 20
DEFAULT_FINANCE_LIMIT = 20


class ReportType(StrEnum):
    """Financial report kinds produced by ``VnstockFinanceSource``."""

    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"
    RATIO = "ratio"


class ReportPeriod(StrEnum):
    """Reporting cadence of a financial report."""

    YEAR = "year"
    QUARTER = "quarter"


class OHLCVInterval(StrEnum):
    """Candle intervals supported by ``VnstockOHLCVSource``."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1H"
    D1 = "1D"
    W1 = "1W"
    MO1 = "1M"
