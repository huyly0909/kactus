"""Gold price service — DuckDB queries and sync."""

from __future__ import annotations

from datetime import date

from kactus_common.exceptions import ConfigurationError
from kactus_data.pipeline import SyncPipeline
from kactus_data.schemas import SyncResult
from kactus_data.sources.gold import (
    GOLD_GLOBAL_TABLE,
    GOLD_VN_TABLE,
    MetalsAPISource,
    VNAppMobGoldSource,
)
from kactus_data.storage.duckdb import DuckDBStorage
from kactus_fin.gold.schema import GoldGlobalItem, GoldVnItem


class GoldService:
    """Query and sync gold price data from DuckDB."""

    # ------------------------------------------------------------------
    # Vietnamese gold
    # ------------------------------------------------------------------

    @staticmethod
    def list_gold_vn(storage: DuckDBStorage, brand: str | None = None) -> list[GoldVnItem]:
        """List Vietnamese gold prices, optionally filtered by brand."""
        if brand:
            df = storage.query(
                "SELECT brand, type, buy_price, sell_price, source, synced_at "
                "FROM gold_vn WHERE brand = ? ORDER BY type",
                [brand.lower()],
            )
        else:
            df = storage.query(
                "SELECT brand, type, buy_price, sell_price, source, synced_at "
                "FROM gold_vn ORDER BY brand, type"
            )
        return [GoldVnItem(**row) for row in df.to_dict("records")]

    @staticmethod
    def sync_gold_vn(storage: DuckDBStorage, brand: str, token: str | None) -> SyncResult:
        """Sync Vietnamese gold prices for a brand."""
        if not token:
            raise ConfigurationError(
                message="VNAppMob token not configured",
                tip="Set KACTUS_VNAPPMOB_TOKEN in .env",
            )
        source = VNAppMobGoldSource(token=token)
        pipeline = SyncPipeline(source=source, storage=storage)
        return pipeline.run(
            table=GOLD_VN_TABLE,
            code=brand.lower(),
            start_date=date.today(),
            end_date=date.today(),
        )

    # ------------------------------------------------------------------
    # Global gold
    # ------------------------------------------------------------------

    @staticmethod
    def list_gold_global(storage: DuckDBStorage, metal: str | None = None) -> list[GoldGlobalItem]:
        """List global metal prices, optionally filtered by metal symbol."""
        if metal:
            df = storage.query(
                "SELECT metal, currency, price, source, synced_at "
                "FROM gold_global WHERE metal = ? ORDER BY currency",
                [metal.upper()],
            )
        else:
            df = storage.query(
                "SELECT metal, currency, price, source, synced_at "
                "FROM gold_global ORDER BY metal, currency"
            )
        return [GoldGlobalItem(**row) for row in df.to_dict("records")]

    @staticmethod
    def sync_gold_global(storage: DuckDBStorage, metal: str, api_key: str | None) -> SyncResult:
        """Sync global metal prices."""
        if not api_key:
            raise ConfigurationError(
                message="Metals-API key not configured",
                tip="Set KACTUS_METALS_API_KEY in .env",
            )
        source = MetalsAPISource(api_key=api_key)
        pipeline = SyncPipeline(source=source, storage=storage)
        return pipeline.run(
            table=GOLD_GLOBAL_TABLE,
            code=metal.upper(),
            start_date=date.today(),
            end_date=date.today(),
        )
