"""Abstract base for vnstock library-based data sources.

Unlike :class:`HttpDataSource` which makes raw HTTP requests,
this wraps the vnstock Python library that returns DataFrames directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from kactus_data.schemas import SyncDataResponse


class VnstockSource(ABC):
    """Base class for data sources backed by the vnstock library.

    Subclasses implement domain-specific logic (OHLCV, company, finance)
    while this class defines the common interface compatible with
    :class:`SyncPipeline`.
    """

    def __init__(self, name: str, source: str = "KBS") -> None:
        self.name = name
        self.source = source

    @abstractmethod
    def sync(
        self,
        start_date: date,
        end_date: date,
        code: str,
    ) -> SyncDataResponse:
        """Fetch data for the given date range and code (symbol).

        Args:
            start_date: Start of the date range.
            end_date: End of the date range.
            code: Stock symbol (e.g. ``VCI``, ``ACB``).

        Returns:
            A :class:`SyncDataResponse` wrapping the fetched data.
        """
        ...
