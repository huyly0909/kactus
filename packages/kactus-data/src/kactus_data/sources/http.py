"""Abstract base for HTTP polling data sources."""

from abc import ABC, abstractmethod
from datetime import date, datetime

import requests

from kactus_data.schemas import SyncDataResponse


class HttpDataSource(ABC):
    """Base class for data sources that fetch data via HTTP requests.

    Subclasses implement domain-specific logic (URL building, auth,
    response parsing) while this class provides the common HTTP
    plumbing.
    """

    def __init__(self, base_url: str, name: str) -> None:
        self.base_url = base_url
        self.name = name

    @abstractmethod
    def sync(
        self,
        start_date: date,
        end_date: date,
        code: str,
    ) -> SyncDataResponse:
        """Fetch data for the given date range and code."""
        ...

    @abstractmethod
    def _format_request_date(self, date_obj: date, is_end_date: bool = False) -> str:
        """Format *date_obj* into the string format the API expects."""
        ...

    @abstractmethod
    def _get_headers(self) -> dict[str, str]:
        """Return HTTP headers required by the API."""
        ...

    @abstractmethod
    def _get_cookies(self) -> dict[str, str]:
        """Return cookies required by the API."""
        ...

    def _make_request(self, url: str, params: dict[str, str]) -> requests.Response:
        """Make an HTTP GET request with headers and cookies."""
        response = requests.get(
            url,
            params=params,
            headers=self._get_headers(),
            cookies=self._get_cookies(),
        )
        response.raise_for_status()
        return response
