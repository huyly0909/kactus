"""World gold price (XAU/USD) from the Yahoo Finance chart API.

Domestic VN gold tracks the world spot price, so this is the global driver
behind every SJC/999 move.  Yahoo's chart endpoint is free, needs no API key and
serves true daily bars back to 2000-08-30.

Two gotchas, both verified live:

* Yahoo's spot symbol ``XAUUSD=X`` is **delisted** ("No data found").  ``GC=F``
  (COMEX gold futures, continuous front-month) is the working replacement — it
  tracks spot closely enough to drive domestic analysis.
* ``range=max`` silently degrades to *monthly* bars.  Explicit
  ``period1``/``period2`` UNIX timestamps with ``interval=1d`` are required to
  get daily data.

Prices are **USD per troy ounce** — not VND — so rows written to the shared gold
board carry an explicit unit.
"""

from datetime import date, datetime, timezone

import requests
from kactus_data.schemas import SyncDataResponse
from kactus_data.sources.http import HttpDataSource

# COMEX gold futures continuous front-month (XAUUSD=X is delisted).
SYMBOL = "GC=F"

# Portfolio code for world gold.
CODE = "XAU"

_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")


class YahooGoldSource(HttpDataSource):
    """Fetch XAU/USD daily bars (USD per troy ounce)."""

    def __init__(self) -> None:
        super().__init__(f"https://{_HOSTS[0]}/v8/finance/chart/{SYMBOL}", "yahoo")

    def sync(
        self,
        start_date: date,
        end_date: date,
        code: str = CODE,
    ) -> SyncDataResponse:
        """Fetch daily XAU/USD bars covering ``start_date..end_date``."""
        params = {
            "period1": self._format_request_date(start_date),
            "period2": self._format_request_date(end_date, is_end_date=True),
            "interval": "1d",
        }

        last_error: Exception | None = None
        for host in _HOSTS:
            url = f"https://{host}/v8/finance/chart/{SYMBOL}"
            try:
                response = self._make_request(url, params)
                return SyncDataResponse(
                    success=True,
                    data_source=self.name,
                    code=code,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    data=self._parse(response.json()),
                    timestamp=datetime.now().isoformat(),
                )
            except (requests.RequestException, ValueError, KeyError, IndexError) as ex:
                # query1 occasionally rejects; fall through to the query2 mirror.
                last_error = ex

        return SyncDataResponse(
            success=False,
            data_source=self.name,
            code=code,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            data=[],
            error={"message": str(last_error)},
            timestamp=datetime.now().isoformat(),
        )

    def latest(self) -> dict | None:
        """Most recent daily bar, or ``None``. Used by the daily quote crawl."""
        today = date.today()
        # A 10-day lookback comfortably clears weekends and market holidays.
        resp = self.sync(date.fromordinal(today.toordinal() - 10), today)
        if not resp.success or not resp.data:
            return None
        return resp.data[-1]

    @staticmethod
    def _parse(payload: dict) -> list[dict]:
        """Flatten Yahoo's columnar chart payload into daily bars."""
        result = payload["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        quote = result["indicators"]["quote"][0]
        bars = []
        for i, ts in enumerate(timestamps):
            close = quote["close"][i]
            if close is None:  # Yahoo pads non-trading days with nulls
                continue
            bars.append(
                {
                    "date": datetime.fromtimestamp(ts, tz=timezone.utc)
                    .date()
                    .isoformat(),
                    "open": quote["open"][i],
                    "high": quote["high"][i],
                    "low": quote["low"][i],
                    "close": close,
                }
            )
        return bars

    def _format_request_date(self, date_obj: date, is_end_date: bool = False) -> str:
        """Yahoo takes UNIX seconds; pad the end so today's bar is included."""
        ts = int(
            datetime(
                date_obj.year, date_obj.month, date_obj.day, tzinfo=timezone.utc
            ).timestamp()
        )
        return str(ts + 86400 if is_end_date else ts)

    def _get_headers(self) -> dict[str, str]:
        # Yahoo rejects requests without a browser-ish User-Agent.
        return {"user-agent": "Mozilla/5.0"}

    def _get_cookies(self) -> dict[str, str]:
        return {}
