"""Metals-API — global precious metal prices (XAU, XAG, XPT, XPD)."""

from datetime import date, datetime

import requests

from kactus_data.schemas import SyncDataResponse
from kactus_data.sources.http import HttpDataSource
from loguru import logger


class MetalsAPISource(HttpDataSource):
    """Fetches global metal prices from Metals-API.

    The ``code`` parameter is a metal symbol: ``XAU``, ``XAG``, ``XPT``, ``XPD``.
    Prices are returned in USD by default.
    """

    SUPPORTED_METALS = ("XAU", "XAG", "XPT", "XPD")

    def __init__(self, api_key: str, base_currency: str = "USD") -> None:
        super().__init__("https://metals-api.com/api", "metals_api")
        self.api_key = api_key
        self.base_currency = base_currency

    def sync(
        self,
        start_date: date,
        end_date: date,
        code: str,
    ) -> SyncDataResponse:
        metal = code.upper()
        if metal not in self.SUPPORTED_METALS:
            return SyncDataResponse(
                success=False,
                data_source=self.name,
                code=code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                data={},
                error=f"Unsupported metal: {code}. Use one of: {', '.join(self.SUPPORTED_METALS)}",
                timestamp=datetime.now().isoformat(),
            )

        url = f"{self.base_url}/latest"
        params = {
            "access_key": self.api_key,
            "base": self.base_currency,
            "symbols": metal,
        }

        try:
            response = self._make_request(url, params)
            data = response.json()

            if not data.get("success", False):
                error_info = data.get("error", {})
                error_msg = error_info.get("info", str(error_info))
                logger.error("Metals-API error for %s: %s", metal, error_msg)
                return SyncDataResponse(
                    success=False,
                    data_source=self.name,
                    code=code,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    data={},
                    error=error_msg,
                    timestamp=datetime.now().isoformat(),
                )

            records = self._parse_response(data, metal)
            logger.info("Fetched %d global gold price(s) for %s", len(records), metal)

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
            logger.error("Metals-API sync failed for %s: %s", metal, ex)
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

    def _parse_response(self, data: dict, metal: str) -> list[dict]:
        """Extract price records from Metals-API response.

        Metals-API returns rates as ``1 / price`` relative to the base
        currency.  We invert to get the conventional price.
        """
        now = datetime.now().isoformat()
        rates = data.get("rates", {})

        records = []
        for symbol, rate in rates.items():
            price = (1.0 / rate) if rate else None
            records.append({
                "metal": symbol,
                "currency": self.base_currency,
                "price": price,
                "source": self.name,
                "synced_at": now,
            })
        return records

    def _format_request_date(self, date_obj: date, is_end_date: bool = False) -> str:
        return date_obj.strftime("%Y-%m-%d")

    def _get_headers(self) -> dict[str, str]:
        return {}

    def _get_cookies(self) -> dict[str, str]:
        return {}
