"""VNStock provider — OHLCV candlestick data and stock listings."""

from __future__ import annotations

from datetime import date

import pandas as pd
from kactus_common.datetimes import utcnow_naive
from kactus_data.schemas import SyncDataResponse
from kactus_data.sources.stock.base import VnstockSource
from kactus_data.util.time import to_event_dt_series
from loguru import logger


class VnstockOHLCVSource(VnstockSource):
    """Fetch OHLCV candlestick data via ``vnstock.Quote.history()``.

    Supports all intervals: ``1m``, ``5m``, ``15m``, ``30m``,
    ``1H``, ``1D``, ``1W``, ``1M``.
    """

    def __init__(self, source: str = "KBS", interval: str = "1D") -> None:
        super().__init__(name="vnstock_ohlcv", source=source)
        self.interval = interval

    def sync(
        self,
        start_date: date,
        end_date: date,
        code: str,
    ) -> SyncDataResponse:
        try:
            from vnstock import Quote

            quote = Quote(symbol=code, source=self.source)
            df: pd.DataFrame = quote.history(
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval=self.interval,
            )

            if df is None or df.empty:
                logger.warning(
                    "No OHLCV data for %s [%s → %s]", code, start_date, end_date
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

            df = df.copy()
            df["symbol"] = code
            df["interval"] = self.interval
            df["source"] = self.source
            # ``time`` from vnstock is naive Vietnam-local (a date for daily
            # intervals, a datetime for intraday). Keep it verbatim and derive
            # the canonical UTC axis into ``event_dt``.
            df["event_dt"] = to_event_dt_series(df["time"])

            records = df.to_dict(orient="records")
            logger.info("Fetched %d OHLCV rows for %s", len(records), code)

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
            logger.error("OHLCV sync failed for %s: %s", code, ex)
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


class VnstockListingSource(VnstockSource):
    """Fetch all listed stock symbols via ``vnstock.Listing.all_symbols()``."""

    def __init__(self, source: str = "KBS") -> None:
        super().__init__(name="vnstock_listing", source=source)

    def sync(
        self,
        start_date: date,
        end_date: date,
        code: str,
    ) -> SyncDataResponse:
        try:
            from vnstock import Listing

            listing = Listing(source=self.source)
            df: pd.DataFrame = listing.all_symbols()

            if df is None or df.empty:
                logger.warning("No listing data returned from %s", self.source)
                return SyncDataResponse(
                    success=True,
                    data_source=self.name,
                    code=code,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    data=[],
                    timestamp=utcnow_naive().isoformat(),
                )

            df = df.copy()
            df["source"] = self.source
            df["synced_at"] = utcnow_naive().isoformat()

            records = df.to_dict(orient="records")
            logger.info("Fetched %d listed symbols from %s", len(records), self.source)

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
            logger.error("Listing sync failed: %s", ex)
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
