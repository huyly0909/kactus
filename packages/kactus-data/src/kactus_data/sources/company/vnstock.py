"""VNStock provider — company overview and details."""

from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd

from kactus_data.schemas import SyncDataResponse
from kactus_data.sources.stock.base import VnstockSource
from loguru import logger


class VnstockCompanySource(VnstockSource):
    """Fetch company overview via ``vnstock.Vnstock().stock().company.overview()``."""

    def __init__(self, source: str = "VCI") -> None:
        super().__init__(name="vnstock_company", source=source)

    def sync(
        self,
        start_date: date,
        end_date: date,
        code: str,
    ) -> SyncDataResponse:
        try:
            from vnstock import Vnstock

            stock = Vnstock().stock(symbol=code, source=self.source)
            overview_df: pd.DataFrame = stock.company.overview()

            if overview_df is None or overview_df.empty:
                logger.warning("No company data for %s", code)
                return SyncDataResponse(
                    success=True,
                    data_source=self.name,
                    code=code,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    data=[],
                    timestamp=datetime.now().isoformat(),
                )

            row = overview_df.iloc[0] if len(overview_df) > 0 else {}
            row_dict = row.to_dict() if hasattr(row, "to_dict") else dict(row)

            record = {
                "symbol": code,
                "company_name": row_dict.get("company_name", row_dict.get("organ_name", "")),
                "short_name": row_dict.get("short_name", row_dict.get("organ_short_name", "")),
                "industry": row_dict.get("industry", row_dict.get("icb_name4", "")),
                "exchange": row_dict.get("exchange", ""),
                "market_cap": row_dict.get("market_cap", None),
                "outstanding_shares": row_dict.get("outstanding_share", None),
                "overview_json": json.dumps(row_dict, default=str, ensure_ascii=False),
                "source": self.source,
                "synced_at": datetime.now().isoformat(),
            }

            logger.info("Fetched company overview for %s", code)

            return SyncDataResponse(
                success=True,
                data_source=self.name,
                code=code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                data=[record],
                timestamp=datetime.now().isoformat(),
            )

        except Exception as ex:
            logger.error("Company sync failed for %s: %s", code, ex)
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
