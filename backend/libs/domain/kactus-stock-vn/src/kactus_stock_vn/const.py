"""Stock API constants — the half of the contract both planes need.

Values mirror what the ETL writes into DuckDB (see
``kactus_data.sources.finance.vnstock.REPORT_TYPES`` and
``VnstockOHLCVSource.interval``), so the API rejects anything that could never
match a stored row instead of silently returning an empty list.

The DuckDB *table names* deliberately do NOT live here — they are a detail of
how the data plane stores rows, not of the wire contract, and belong with the
SQL in ``kactus_data.market.const``. The generic OLAP read cap (``MAX_LIMIT``)
is infrastructure and stays in ``kactus_common.database.duckdb.consts``.
"""

from __future__ import annotations

from enum import StrEnum

# Per-endpoint default read limits.
DEFAULT_OHLCV_LIMIT = 500
DEFAULT_LIST_LIMIT = 50
DEFAULT_NEWS_LIMIT = 20
DEFAULT_FINANCE_LIMIT = 20
DEFAULT_EVENTS_LIMIT = 20
DEFAULT_DAILY_LIMIT = 20

# A TTM figure is exactly four quarters; fewer means the window is incomplete
# and the caller is told so rather than shown a short sum as if it were annual.
TTM_QUARTERS = 4


class TechnicalInterval(StrEnum):
    """Candle aggregation a technical reading is computed over.

    Deliberately narrower than :class:`OHLCVInterval`: weekly and monthly bars
    are rolled up from stored dailies, and intraday intervals are not stored
    deeply enough for a 200-period average to mean anything.
    """

    D1 = "1D"
    W1 = "1W"
    MO1 = "1M"


class TechnicalSignal(StrEnum):
    """Vote a single indicator casts."""

    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"


class TechnicalConsensus(StrEnum):
    """Aggregate reading across all indicators that had enough history."""

    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"
    NO_DATA = "NO_DATA"


class SignalGroup(StrEnum):
    """Which family an indicator belongs to, for grouped display."""

    OSCILLATOR = "oscillator"
    MOVING_AVERAGE = "moving_average"


class PeerBasis(StrEnum):
    """What cohort a fundamental score was ranked against.

    The UI must not caption a fallback as a sector comparison, so the basis
    travels with the result rather than being inferred from the peer count.
    """

    SECTOR = "sector"
    VN30_NONBANK = "vn30_nonbank"
    VN30_BANKS = "vn30_banks"


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
