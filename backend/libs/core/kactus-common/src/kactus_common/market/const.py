"""Market API constants — the half of the contract both planes need.

Values mirror what the ETL writes into DuckDB (see
``kactus_data.sources.finance.vnstock.REPORT_TYPES`` and
``VnstockOHLCVSource.interval``), so the API rejects anything that could never
match a stored row instead of silently returning an empty list.

The DuckDB *table names* deliberately do NOT live here — they are a detail of
how the data plane stores rows, not of the wire contract, and belong with the
SQL in ``kactus_data.market.const``.
"""

from __future__ import annotations

from enum import StrEnum

# Read caps — the OLAP tables are unbounded, the API is not.
MAX_LIMIT = 2000
# Gold history gets its own cap: the XAU series alone is ~6.5k daily points,
# so the global MAX_LIMIT would silently truncate a "Max" range request.
DEFAULT_GOLD_HISTORY_LIMIT = 2500
GOLD_HISTORY_MAX_LIMIT = 10_000
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
