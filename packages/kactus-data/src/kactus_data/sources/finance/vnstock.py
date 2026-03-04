"""VNStock provider — financial statements and ratios."""

from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd

from kactus_data.schemas import SyncDataResponse
from kactus_data.sources.stock.base import VnstockSource
from loguru import logger

REPORT_TYPES = ("income_statement", "balance_sheet", "cash_flow", "ratio")


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
            raise ValueError(f"report_type must be one of {REPORT_TYPES}, got '{report_type}'")
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
                    timestamp=datetime.now().isoformat(),
                )

            records = []
            for _, row in df.iterrows():
                row_dict = row.to_dict()
                year = int(row_dict.get("year", row_dict.get("Year", 0)))
                quarter = int(row_dict.get("quarter", row_dict.get("Quarter", 0)))

                records.append({
                    "symbol": code,
                    "period": self.period,
                    "year": year,
                    "quarter": quarter,
                    "report_type": self.report_type,
                    "data_json": json.dumps(row_dict, default=str, ensure_ascii=False),
                    "source": self.source,
                    "synced_at": datetime.now().isoformat(),
                })

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
                timestamp=datetime.now().isoformat(),
            )

        except Exception as ex:
            logger.error("Finance sync (%s) failed for %s: %s", self.report_type, code, ex)
            return SyncDataResponse(
                success=False,
                data_source=self.name,
                code=code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                data={},
                error={"message": str(ex)},
                timestamp=datetime.now().isoformat(),
            )
