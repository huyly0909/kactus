"""Mihong.vn gold price data source (api.mihong.vn)."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import requests
from kactus_data.schemas import SyncDataResponse
from kactus_data.sources.http import HttpDataSource

# Domestic gold codes the API accepts.  SJC and 999 are the liquid retail types;
# the rest are jewelry/karat grades.  DOJI / PNJ / 24K are rejected with HTTP 400.
SUPPORTED_CODES = frozenset(
    {"SJC", "999", "950", "985", "980", "750", "680", "610", "580", "410"}
)

# mihong quotes domestic gold per *chỉ*; the price board stores VND per lượng.
CHI_TO_LUONG = 10

# Response ``dateTime`` shape, e.g. ``"30/06/2025 00:00"``.
_DATETIME_FORMAT = "%d/%m/%Y %H:%M"
_QUANT = Decimal("0.0001")


class MihongGoldSource(HttpDataSource):
    """Fetch gold prices from the public mihong.vn API.

    The legacy ``www.mihong.vn/api/v1/gold/prices/codes`` host is gone (it now
    serves the static SPA), and the ``startDate``/``endDate`` range query on the
    new host is dead — it validates the dates but always returns ``[]``.  The
    live shape is a trailing window via ``last``:

    ==========  ==========================================================
    ``last``    returns
    ==========  ==========================================================
    ``1h``      intraday, 5-minute ticks
    ``24h``     intraday, ~87 ticks
    ``15d``     one point per day
    ``1M``      one point per day (~29 points)
    ``6M``      end-of-month snapshots only
    ``1y``      end-of-month snapshots only (deepest: ~13 months)
    ==========  ==========================================================

    So this source is good for *daily* and *intraday* data but cannot backfill
    arbitrary history — there is no ``5y``/``all`` window.  No auth, cookie or
    XSRF token is required.

    Prices are **VND per chỉ** (1/10 lượng); multiply by :data:`CHI_TO_LUONG`
    for VND/lượng.
    """

    def __init__(self, xsrf_token: str | None = None) -> None:
        # ``xsrf_token`` is accepted for backwards compatibility only — the
        # api.mihong.vn endpoint is unauthenticated.
        super().__init__("https://api.mihong.vn/v1/gold-prices", "mihong")
        self.xsrf_token = xsrf_token or ""

    def sync(
        self,
        start_date: date,
        end_date: date,
        code: str,
    ) -> SyncDataResponse:
        """Fetch the mihong price series for *code* covering the given range.

        The API has no arbitrary from/to, so the range is mapped to the smallest
        ``last`` window that spans it.  A same-day request (``start == end``)
        uses ``last=24h`` so the newest intraday tick — the current price — is
        the last element of the returned list.
        """
        params = {
            "market": "domestic",
            "goldCode": code,
            "last": self._window_for(start_date, end_date),
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

    def history(
        self,
        start_date: date,
        end_date: date,
        code: str,
    ) -> list[dict]:
        """Mihong series for *code* over ``start..end`` (VND/lượng), oldest first.

        Reuses :meth:`sync` (the trailing ``last=`` window) but parses the
        **full** flat array, not just the newest tick. Granularity is inherent
        in the returned dates: ``15d``/``1M`` give one point per day, ``6M``/
        ``1y`` give end-of-month points only — we store each at its actual date.
        Points are clipped to the requested ``[start, end]`` (the ``last=``
        window can be wider) and scaled VND/chỉ → VND/lượng as ``Decimal``.

        Returns ``[{date, buy_price, sell_price}]``; ``[]`` on a failed fetch.
        """
        response = self.sync(start_date, end_date, code)
        if not response.success or not isinstance(response.data, list):
            return []

        by_day: dict[date, tuple[Decimal | None, Decimal | None]] = {}
        for point in response.data:
            parsed = _parse_point(point)
            if parsed is None:
                continue
            day, buy, sell = parsed
            if day < start_date or day > end_date:
                continue
            by_day[day] = (buy, sell)  # a repeated day keeps the latest point
        return [
            {"date": day, "buy_price": by_day[day][0], "sell_price": by_day[day][1]}
            for day in sorted(by_day)
        ]

    @staticmethod
    def _window_for(start_date: date, end_date: date) -> str:
        """Smallest supported ``last`` window covering ``start_date..end_date``."""
        span_days = (end_date - start_date).days
        if span_days <= 1:
            return "24h"
        if span_days <= 15:
            return "15d"
        if span_days <= 31:
            return "1M"
        if span_days <= 186:
            return "6M"
        return "1y"

    def _format_request_date(self, date_obj: date, is_end_date: bool = False) -> str:
        """Kept to satisfy the base class — the ``last`` API takes no dates."""
        return date_obj.isoformat()

    def _get_headers(self) -> dict[str, str]:
        return {
            "referer": "https://www.mihong.vn/",
            "x-market": "mihong",
        }

    def _get_cookies(self) -> dict[str, str]:
        return {}


def _mihong_decimal(value) -> Decimal | None:
    """VND/chỉ → VND/lượng ``Decimal`` (×10, 4dp); blank/0/garbage → ``None``.

    Goes via ``str`` and stays ``Decimal`` throughout (``Decimal * int`` is
    safe; ``Decimal * float`` would raise) so VND gold keeps full precision.
    """
    if value is None or value == "":
        return None
    try:
        result = (Decimal(str(value)) * CHI_TO_LUONG).quantize(_QUANT)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return None if result == 0 else result


def _parse_point(point: dict) -> tuple[date, Decimal | None, Decimal | None] | None:
    """``(day, buy, sell)`` from one series point, or ``None`` to skip it."""
    raw_dt = point.get("dateTime")
    if not raw_dt:
        return None
    try:
        day = datetime.strptime(raw_dt, _DATETIME_FORMAT).date()
    except (ValueError, TypeError):
        return None
    buy = _mihong_decimal(point.get("buyingPrice"))
    sell = _mihong_decimal(point.get("sellingPrice"))
    if buy is None and sell is None:
        return None
    return day, buy, sell
