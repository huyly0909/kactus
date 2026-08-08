"""VNStock provider — financial statements and ratios."""

from __future__ import annotations

import json
import re
from datetime import date

import pandas as pd
from kactus_common.datetimes import utcnow_naive
from kactus_data.config import get_settings
from kactus_data.schemas import SyncDataResponse
from kactus_data.sources.stock.base import VnstockSource
from loguru import logger

REPORT_TYPES = ("income_statement", "balance_sheet", "cash_flow", "ratio")

# vnstock 4.x returns statements **transposed** — metrics as rows, periods as
# column headers ("2025", "2025-Q3"). Reading year/quarter out of row cells then
# yields 0/0 for every row, and since the OLAP primary key is
# (symbol, period, year, quarter, report_type) the whole statement history
# collapses onto a single row. ``ratios`` already pivots for this reason
# (see kactus_data.sources.stock.market._ratio_rows); statements did not.
_PERIOD_RE = re.compile(r"^(\d{4})(?:[-_/ ]?Q?([1-4]))?$")
_LABEL_COLS = ("item_id", "item", "item_en")


def _period_pivot(df: pd.DataFrame) -> list[tuple[str, int, int, dict]]:
    """Transposed frame → ``[(period_label, year, quarter, {metric: value})]``.

    Returns an empty list for a tidy frame (no period-shaped headers), which
    tells the caller to fall back to one-row-per-record.
    """
    cols = list(df.columns)
    period_cols = [c for c in cols if _PERIOD_RE.match(str(c).strip())]
    if not period_cols:
        return []
    label_col = next((c for c in _LABEL_COLS if c in cols), None)
    records = df.to_dict(orient="records")
    out: list[tuple[str, int, int, dict]] = []
    for col in period_cols:
        label = str(col).strip()
        m = _PERIOD_RE.match(label)
        if m is None:  # pragma: no cover - filtered above
            continue
        metrics = {}
        for r in records:
            key = r.get(label_col) if label_col else None
            if key is not None and pd.notna(key):
                metrics[str(key)] = r.get(col)
        out.append((label, int(m.group(1)), int(m.group(2) or 0), metrics))
    return out


class VnstockFinanceSource(VnstockSource):
    """Fetch financial reports via ``vnstock.Finance``.

    Supports four report types: ``income_statement``, ``balance_sheet``,
    ``cash_flow``, ``ratio``.
    """

    def __init__(
        self,
        source: str = "KBS",
        report_type: str = "income_statement",
        period: str = "quarter",
    ) -> None:
        if report_type not in REPORT_TYPES:
            raise ValueError(
                f"report_type must be one of {REPORT_TYPES}, got '{report_type}'"
            )
        get_settings()  # side effect: registers settings in the global registry
        super().__init__(name=f"vnstock_finance_{report_type}", source=source)
        self.report_type = report_type
        self.period = period

    def sync(
        self,
        start_date: date,
        end_date: date,
        code: str,
    ) -> SyncDataResponse:
        try:
            from vnstock import Finance

            finance = Finance(source=self.source, symbol=code)
            method = getattr(finance, self.report_type)
            df: pd.DataFrame = method(period=self.period)

            if df is None or df.empty:
                logger.warning(
                    "No %s data for %s (period=%s)",
                    self.report_type,
                    code,
                    self.period,
                )
                return SyncDataResponse(
                    success=True,
                    data_source=self.name,
                    code=code,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    data=[],
                    timestamp=utcnow_naive().isoformat(),
                )

            if isinstance(df.columns, pd.MultiIndex):
                df = df.copy()
                df.columns = [
                    "_".join(str(p) for p in tup if p != "") for tup in df.columns
                ]

            now = utcnow_naive().isoformat()
            records = []
            pivoted = _period_pivot(df)
            if pivoted:
                # ``period`` holds the real label ("2025-Q3") rather than the
                # requested granularity, so each period is its own row under the
                # (symbol, period, year, quarter, report_type) key.
                for label, year, quarter, metrics in pivoted:
                    records.append(
                        {
                            "symbol": code,
                            "period": label,
                            "year": year,
                            "quarter": quarter,
                            "report_type": self.report_type,
                            "data_json": json.dumps(
                                metrics, default=str, ensure_ascii=False
                            ),
                            "source": self.source,
                            "synced_at": now,
                        }
                    )
            else:  # tidy frame — older shapes keep year/quarter in cells
                for _, row in df.iterrows():
                    row_dict = row.to_dict()
                    records.append(
                        {
                            "symbol": code,
                            "period": self.period,
                            "year": int(row_dict.get("year", row_dict.get("Year", 0))),
                            "quarter": int(
                                row_dict.get("quarter", row_dict.get("Quarter", 0))
                            ),
                            "report_type": self.report_type,
                            "data_json": json.dumps(
                                row_dict, default=str, ensure_ascii=False
                            ),
                            "source": self.source,
                            "synced_at": now,
                        }
                    )

            logger.info(
                "Fetched %d %s records for %s (period=%s)",
                len(records),
                self.report_type,
                code,
                self.period,
            )

            return SyncDataResponse(
                success=True,
                data_source=self.name,
                code=code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                data=records,
                timestamp=utcnow_naive().isoformat(),
            )

        except Exception as ex:
            logger.error(
                "Finance sync (%s) failed for %s: %s", self.report_type, code, ex
            )
            return SyncDataResponse(
                success=False,
                data_source=self.name,
                code=code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                data={},
                error={"message": str(ex)},
                timestamp=utcnow_naive().isoformat(),
            )
