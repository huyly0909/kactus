"""Stock data service — DuckDB queries and sync."""

from __future__ import annotations

from datetime import date

from kactus_data.pipeline import SyncPipeline
from kactus_data.schemas import SyncResult
from kactus_data.sources.stock import (
    STOCK_LISTING_TABLE,
    STOCK_OHLCV_TABLE,
    VnstockListingSource,
    VnstockOHLCVSource,
)
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_fin.stock.schema import OhlcvItem, StockListingItem


class StockService:
    """Query and sync stock data from DuckDB."""

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    @staticmethod
    def list_stocks(storage: DuckDBStorage) -> list[StockListingItem]:
        """List all stock listings."""
        df = storage.query(
            "SELECT symbol, organ_name, source, synced_at "
            "FROM stock_listing ORDER BY symbol"
        )
        return [StockListingItem(**row) for row in df.to_dict("records")]

    @staticmethod
    def sync_listing(storage: DuckDBStorage) -> SyncResult:
        """Sync all stock listings."""
        source = VnstockListingSource()
        pipeline = SyncPipeline(source=source, storage=storage)
        return pipeline.run(
            table=STOCK_LISTING_TABLE,
            code="ALL",
            start_date=date.today(),
            end_date=date.today(),
        )

    # ------------------------------------------------------------------
    # OHLCV
    # ------------------------------------------------------------------

    @staticmethod
    def get_ohlcv(storage: DuckDBStorage, symbol: str) -> list[OhlcvItem]:
        """Get OHLCV data for a symbol."""
        df = storage.query(
            f"SELECT symbol, time, interval, open, high, low, close, volume, source "
            f"FROM stock_ohlcv WHERE symbol = '{symbol}' "
            f"ORDER BY time DESC LIMIT 200"
        )
        return [OhlcvItem(**row) for row in df.to_dict("records")]

    @staticmethod
    def sync_ohlcv(
        storage: DuckDBStorage,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> SyncResult:
        """Sync OHLCV data for a symbol and date range."""
        source = VnstockOHLCVSource()
        pipeline = SyncPipeline(source=source, storage=storage)
        return pipeline.run(
            table=STOCK_OHLCV_TABLE,
            code=symbol,
            start_date=start_date,
            end_date=end_date,
        )
