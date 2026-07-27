"""SJC official gold price source (sjc.com.vn).

SJC issues the reference price for the SJC gold bar, so this is the
authoritative domestic quote — mihong and the jewellery chains all track it.

The endpoint sits behind a Cloudflare managed challenge: plain ``requests``
(and plain ``curl``) get an HTTP 403 challenge page, so we go through
``curl_cffi`` with Chrome TLS impersonation — the same technique the Zalo PA
notification channel already uses.  No API key or cookie is needed.

Unlike :class:`~kactus_data.sources.gold.mihong.MihongGoldSource` this is not an
:class:`HttpDataSource`: one POST returns the whole board (every gold type and
branch) rather than one series per code, and it speaks POST-with-form-body
instead of GET-with-params.

Prices are already **VND per lượng** (``BuyValue`` / ``SellValue``).
"""

import re
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from curl_cffi import requests as curl_requests
from loguru import logger

ENDPOINT = "https://sjc.com.vn/GoldPrice/Services/PriceService.ashx"

# Hồ Chí Minh is the reference branch quoted as "the" SJC price.
REFERENCE_BRANCH = "Hồ Chí Minh"

# --- History (GetGoldPriceHistory) --------------------------------------- #
# ``goldPriceId`` for the HCM reference branch (matches REFERENCE_BRANCH).
# Others: 2 = Miền Bắc, 5 = Cà Mau, 10 = Quảng Ngãi.
HISTORY_BRANCH_ID = "1"
# The API caps a single request at ~85 days, so we page in 80-day windows.
HISTORY_WINDOW_DAYS = 80
# GetGoldPriceHistory returns *only* the SJC 1L bar series (no 999 ring, no
# multi-type) — verified against sjc.com.vn; the 999 series has no SJC history
# and backfills from Mihong's 1-year window instead.
_GROUP_DATE_RE = re.compile(r"/Date\((\d+)\)/")
_VN_TZ = timezone(timedelta(hours=7))
_QUANT = Decimal("0.0001")


def history_windows(
    start: date, end: date, step: int = HISTORY_WINDOW_DAYS
) -> Iterator[tuple[date, date]]:
    """Yield disjoint ``[from, to]`` windows (≤ ``step`` days) covering the range.

    Exposed so a caller (the backfill job handler) can report progress per
    window while calling :meth:`SjcGoldSource.history` on each.
    """
    cur = start
    while cur <= end:
        win_end = min(cur + timedelta(days=step - 1), end)
        yield cur, win_end
        cur = win_end + timedelta(days=1)


# Portfolio code -> SJC ``TypeName``.  SJC publishes the gold bar and its own
# 99,99% ring; DOJI/PNJ are other companies' products and are not on this board.
CODE_TO_TYPE_NAME = {
    "SJC": "Vàng SJC 1L, 10L, 1KG",
    "999": "Vàng nhẫn SJC 99,99% 1 chỉ, 2 chỉ, 5 chỉ",
}

SUPPORTED_CODES = frozenset(CODE_TO_TYPE_NAME)


class SjcGoldSource:
    """Fetch the current SJC gold board (all types/branches, VND/lượng)."""

    name = "sjc"

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def fetch_board(self) -> list[dict]:
        """Return the raw SJC price rows, or ``[]`` if the board is unreachable.

        Never raises: a Cloudflare block or network blip must degrade the gold
        crawl to its fallback source, not abort it.
        """
        try:
            response = curl_requests.post(
                ENDPOINT,
                headers={
                    "referer": "https://sjc.com.vn/",
                    "x-requested-with": "XMLHttpRequest",
                },
                impersonate="chrome",
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as ex:  # noqa: BLE001 - network/Cloudflare/JSON all non-fatal
            logger.warning("SJC gold board fetch failed: {err}", err=str(ex))
            return []

        if not isinstance(payload, dict) or not payload.get("success"):
            logger.warning("SJC gold board returned no data")
            return []
        return payload.get("data") or []

    def history(self, start: date, end: date) -> list[dict]:
        """Daily SJC 1L bar series for ``start..end`` (VND/lượng), oldest first.

        Ports ``GetGoldPriceHistory`` (reaches ~2009). The response is intraday
        ticks; we reduce to one row per calendar day (last tick = the close).
        Paginates internally in :data:`HISTORY_WINDOW_DAYS`-day windows, so it is
        correct for any range — but a caller wanting per-window progress should
        drive :func:`history_windows` and call this once per window.

        Returns ``[{date, buy_price, sell_price}]`` with ``Decimal`` prices (VND
        gold ~1.4e8 loses precision as ``float``). Never raises: a Cloudflare
        block or blip yields ``[]`` for that window, degrading the backfill
        rather than aborting it.
        """
        session = curl_requests.Session()
        # day -> (tick_ms, buy, sell); the newest tick of the day wins.
        daily: dict[date, tuple[int, Decimal | None, Decimal | None]] = {}
        for frm, to in history_windows(start, end):
            for row in self._fetch_history(session, frm, to):
                parsed = _parse_history_row(row)
                if parsed is None:
                    continue
                day, ts_ms, buy, sell = parsed
                prev = daily.get(day)
                if prev is None or ts_ms >= prev[0]:
                    daily[day] = (ts_ms, buy, sell)
        return [
            {"date": day, "buy_price": daily[day][1], "sell_price": daily[day][2]}
            for day in sorted(daily)
        ]

    def _fetch_history(
        self, session: "curl_requests.Session", frm: date, to: date
    ) -> list[dict]:
        """One ``GetGoldPriceHistory`` window request; ``[]`` on any failure."""
        try:
            response = session.post(
                ENDPOINT,
                headers={
                    "referer": "https://sjc.com.vn/",
                    "x-requested-with": "XMLHttpRequest",
                },
                data={
                    "method": "GetGoldPriceHistory",
                    "goldPriceId": HISTORY_BRANCH_ID,
                    "fromDate": frm.strftime("%d/%m/%Y"),
                    "toDate": to.strftime("%d/%m/%Y"),
                },
                impersonate="chrome",
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as ex:  # noqa: BLE001 - network/Cloudflare/JSON non-fatal
            logger.warning(
                "SJC gold history {a}..{b} failed: {err}",
                a=frm,
                b=to,
                err=str(ex),
            )
            return []
        if not isinstance(payload, dict):
            return []
        return payload.get("data") or []

    def quote(self, code: str, board: list[dict] | None = None) -> dict | None:
        """Return the reference-branch quote for *code*, or ``None``.

        Pass a pre-fetched *board* to price several codes from a single request.
        """
        type_name = CODE_TO_TYPE_NAME.get(str(code).upper())
        if type_name is None:
            return None

        rows = self.fetch_board() if board is None else board
        for row in rows:
            if (
                row.get("TypeName") == type_name
                and row.get("BranchName") == REFERENCE_BRANCH
            ):
                return {
                    "buy_price": _as_float(row.get("BuyValue")),
                    "sell_price": _as_float(row.get("SellValue")),
                    "raw": row,
                }
        return None


def _as_float(value) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _as_decimal(value) -> Decimal | None:
    """History price → 4dp ``Decimal``; blank/0/garbage → ``None``.

    ``0`` is SJC's "no quote for this tick" sentinel, so it maps to ``None``
    (NULL) rather than a real zero price. Goes via ``str`` to keep VND integers
    exact (never through ``float``).
    """
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value)).quantize(_QUANT)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return None if result == 0 else result


def _parse_history_row(
    row: dict,
) -> tuple[date, int, Decimal | None, Decimal | None] | None:
    """``(day, tick_ms, buy, sell)`` from a history tick, or ``None`` to skip.

    Skips a row with no parseable ``GroupDate`` or with neither price set.
    """
    match = _GROUP_DATE_RE.search(row.get("GroupDate", "") or "")
    if not match:
        return None
    ts_ms = int(match.group(1))
    day = datetime.fromtimestamp(ts_ms / 1000, tz=_VN_TZ).date()
    buy = _as_decimal(row.get("BuyValue"))
    sell = _as_decimal(row.get("SellValue"))
    if buy is None and sell is None:
        return None
    return day, ts_ms, buy, sell
