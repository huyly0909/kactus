"""Mihong.vn gold price data source."""

from datetime import date, datetime

import requests

from kactus_data.schemas import SyncDataResponse
from kactus_data.sources.http import HttpDataSource


class MihongGoldSource(HttpDataSource):
    """Fetches gold price data from mihong.vn API."""

    def __init__(self, xsrf_token: str) -> None:
        super().__init__("https://www.mihong.vn/api/v1/gold/prices/codes", "mihong")
        self.xsrf_token = xsrf_token

    def sync(
        self,
        start_date: date,
        end_date: date,
        code: str,
    ) -> SyncDataResponse:
        """Sync gold price data from Mihong API."""
        params = {
            "code": code,
            "startDate": self._format_request_date(start_date, is_end_date=False),
            "endDate": self._format_request_date(end_date, is_end_date=True),
        }

        try:
            response = self._make_request(self.base_url, params)
            data = response.json()

            return SyncDataResponse(
                success=True,
                data_source=self.name,
                code=code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                data=data,
                timestamp=datetime.now().isoformat(),
            )

        except requests.RequestException as ex:
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

    def _format_request_date(self, date_obj: date, is_end_date: bool = False) -> str:
        """Format date for Mihong API: ``M/d/yyyy HH:mm:ss``."""
        if isinstance(date_obj, datetime):
            return date_obj.strftime("%-m/%-d/%Y %H:%M:%S")
        if is_end_date:
            dt = datetime.combine(date_obj, datetime.max.time().replace(microsecond=0))
        else:
            dt = datetime.combine(date_obj, datetime.min.time())
        return dt.strftime("%-m/%-d/%Y %H:%M:%S")

    def _get_headers(self) -> dict[str, str]:
        return {
            "referer": "https://www.mihong.vn/vi/gia-vang-trong-nuoc",
            "x-requested-with": "XMLHttpRequest",
        }

    def _get_cookies(self) -> dict[str, str]:
        return {"XSRF-TOKEN": self.xsrf_token}
