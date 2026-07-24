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

from curl_cffi import requests as curl_requests
from loguru import logger

ENDPOINT = "https://sjc.com.vn/GoldPrice/Services/PriceService.ashx"

# Hồ Chí Minh is the reference branch quoted as "the" SJC price.
REFERENCE_BRANCH = "Hồ Chí Minh"

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
