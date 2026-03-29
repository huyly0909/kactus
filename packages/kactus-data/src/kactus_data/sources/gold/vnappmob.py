"""VNAppMob Gold API v2 — Vietnamese domestic gold prices (SJC, DOJI, PNJ)."""

from datetime import date, datetime

import requests

from kactus_data.schemas import SyncDataResponse
from kactus_data.sources.http import HttpDataSource
from loguru import logger


class VNAppMobGoldSource(HttpDataSource):
    """Fetches Vietnamese gold prices from VNAppMob API v2.

    Supported brands (passed as ``code``): ``sjc``, ``doji``, ``pnj``.

    Each brand endpoint returns buy/sell prices for different gold types.
    """

    SUPPORTED_BRANDS = ("sjc", "doji", "pnj")

    def __init__(self, token: str) -> None:
        super().__init__("https://vapi.vnappmob.com/api/v2/gold", "vnappmob_gold")
        self.token = token

    def sync(
        self,
        start_date: date,
        end_date: date,
        code: str,
    ) -> SyncDataResponse:
        brand = code.lower()
        if brand not in self.SUPPORTED_BRANDS:
            return SyncDataResponse(
                success=False,
                data_source=self.name,
                code=code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                data={},
                error=f"Unsupported brand: {code}. Use one of: {', '.join(self.SUPPORTED_BRANDS)}",
                timestamp=datetime.now().isoformat(),
            )

        url = f"{self.base_url}/{brand}"
        try:
            response = self._make_request(url, params={})
            data = response.json()

            # Normalise response into flat records
            records = self._parse_response(data, brand)
            logger.info("Fetched %d gold prices for %s", len(records), brand)

            return SyncDataResponse(
                success=True,
                data_source=self.name,
                code=code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                data=records,
                timestamp=datetime.now().isoformat(),
            )

        except requests.RequestException as ex:
            logger.error("VNAppMob gold sync failed for %s: %s", brand, ex)
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

    def _parse_response(self, data: dict | list, brand: str) -> list[dict]:
        """Normalise API response into flat records for DuckDB storage."""
        now = datetime.now().isoformat()

        # VNAppMob returns a list of gold type entries
        items = data if isinstance(data, list) else data.get("data", data.get("results", []))
        if not isinstance(items, list):
            items = [items] if items else []

        records = []
        for item in items:
            if not isinstance(item, dict):
                continue
            records.append({
                "brand": brand,
                "type": item.get("type", item.get("name", "")),
                "buy_price": self._parse_price(item.get("buy", item.get("buyPrice"))),
                "sell_price": self._parse_price(item.get("sell", item.get("sellPrice"))),
                "source": self.name,
                "synced_at": now,
            })
        return records

    @staticmethod
    def _parse_price(value: str | float | int | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            cleaned = str(value).replace(",", "").replace(" ", "").strip()
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None

    def _format_request_date(self, date_obj: date, is_end_date: bool = False) -> str:
        return date_obj.isoformat()

    def _get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _get_cookies(self) -> dict[str, str]:
        return {}
