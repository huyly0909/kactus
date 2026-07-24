"""HTTP client for the data plane — the replacement for direct DuckDB access.

DuckDB permits one read-write process or several read-only ones, never both
across processes. Once kactus-data-server owns the write handle, kactus-fin
cannot open the file at all, so every market read became a network call. There
is no "read it directly, just for this one cheap query" option; that is the real
cost of the split, and this module is where it is paid.

The method surface deliberately mirrors ``MarketService`` and the old
``provider.read`` one-for-one, so each endpoint in ``market/api.py`` and
``portfolio/api.py`` swapped a call for a call and nothing else.

Failures surface as :class:`ExternalServiceError` (→ 502). A market read that
cannot reach the data plane is not an empty result — returning ``[]`` there
would render an empty portfolio to a user who owns ten positions, which is a
worse lie than an error.
"""

from __future__ import annotations

import datetime
from typing import Any

import httpx
from kactus_common.config import settings
from kactus_common.exceptions import ExternalServiceError
from kactus_common.market.schema import (
    FinanceReportSchema,
    GoldPriceSchema,
    OHLCVSchema,
    StockDetailSchema,
    StockListingSchema,
    StockNewsSchema,
    StockQuoteSchema,
)
from kactus_common.portfolio.const import AssetType, CrawlKind, CrawlTrigger
from kactus_common.portfolio.schema import (
    CrawlRequest,
    CrawlStatusSchema,
    CrawlTriggerResponse,
    MarketRowSchema,
)
from loguru import logger

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """Return the process-wide async HTTP client.

    Built lazily and kept, so connections are pooled and TLS/TCP setup is not
    repeated per request — a portfolio page can issue several of these.
    """
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=str(settings.data_plane_url).rstrip("/"),
            headers={"X-Service-Token": settings.internal_service_token},
            timeout=float(getattr(settings, "data_plane_timeout", 30.0)),
        )
    return _client


async def close_client() -> None:
    """Close the pool — called from the app lifespan's shutdown half."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def reset_client() -> None:
    """Drop the cached client without awaiting (tests)."""
    global _client
    _client = None


async def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET *path* and unwrap the ``ResponseModel`` envelope."""
    return await _request("GET", path, params=params)


async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: Any | None = None,
) -> Any:
    try:
        resp = await get_client().request(method, path, params=params, json=json)
        resp.raise_for_status()
    except httpx.HTTPStatusError as ex:
        # The data plane speaks the same error envelope, so pass its message
        # through instead of a generic one — "invalid X-Service-Token" is a
        # far more actionable log line than "502 from data plane".
        detail = _envelope_message(ex.response)
        logger.error(
            f"Data plane {method} {path} → {ex.response.status_code}: {detail}"
        )
        raise ExternalServiceError(f"Data plane request failed: {detail}") from ex
    except httpx.HTTPError as ex:
        logger.error(f"Data plane {method} {path} unreachable: {ex}")
        raise ExternalServiceError(f"Data plane is unreachable: {ex}") from ex

    body = resp.json()
    return body.get("data") if isinstance(body, dict) else body


def _envelope_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body, dict):
        # ``message`` is what KactusException.to_dict() emits; ``detail`` is
        # FastAPI's own shape, which the 422 from request validation still uses.
        return str(body.get("message") or body.get("detail") or body)[:200]
    return str(body)[:200]


def _clean(params: dict[str, Any]) -> dict[str, Any]:
    """Drop ``None`` values so they are not sent as the literal string 'None'."""
    return {k: v for k, v in params.items() if v is not None}


# --------------------------------------------------------------------------- #
# Market reads — mirrors MarketService
# --------------------------------------------------------------------------- #
async def list_gold(*, codes: list[str] | None = None) -> list[GoldPriceSchema]:
    rows = await _get("/internal/market/gold", _clean({"code": codes}))
    return [GoldPriceSchema.model_validate(r) for r in rows]


async def search_stocks(
    *, q: str | None = None, limit: int = 50
) -> list[StockListingSchema]:
    rows = await _get("/internal/market/stocks", _clean({"q": q, "limit": limit}))
    return [StockListingSchema.model_validate(r) for r in rows]


async def list_quotes(
    *, symbols: list[str] | None = None, limit: int = 50
) -> list[StockQuoteSchema]:
    rows = await _get(
        "/internal/market/stocks/quotes", _clean({"symbol": symbols, "limit": limit})
    )
    return [StockQuoteSchema.model_validate(r) for r in rows]


async def get_stock(symbol: str) -> StockDetailSchema | None:
    row = await _get(f"/internal/market/stocks/{symbol}")
    return StockDetailSchema.model_validate(row) if row else None


async def list_ohlcv(
    symbol: str,
    *,
    interval: str = "1D",
    start: datetime.date | None = None,
    end: datetime.date | None = None,
    limit: int = 500,
) -> list[OHLCVSchema]:
    rows = await _get(
        f"/internal/market/stocks/{symbol}/ohlcv",
        _clean(
            {
                "interval": interval,
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
                "limit": limit,
            }
        ),
    )
    return [OHLCVSchema.model_validate(r) for r in rows]


async def list_news(symbol: str, *, limit: int = 20) -> list[StockNewsSchema]:
    rows = await _get(f"/internal/market/stocks/{symbol}/news", {"limit": limit})
    return [StockNewsSchema.model_validate(r) for r in rows]


async def list_finance(
    symbol: str,
    *,
    report_type: str,
    period: str | None = None,
    limit: int = 20,
) -> list[FinanceReportSchema]:
    rows = await _get(
        f"/internal/market/stocks/{symbol}/finance",
        _clean({"report_type": report_type, "period": period, "limit": limit}),
    )
    return [FinanceReportSchema.model_validate(r) for r in rows]


# --------------------------------------------------------------------------- #
# Asset rows — mirrors provider.read(kind, codes)
# --------------------------------------------------------------------------- #
async def read_assets(
    asset_type: AssetType, kind: CrawlKind, codes: list[str]
) -> list[MarketRowSchema]:
    """Stored rows for ``codes``; empty when the provider has no such dataset."""
    if not codes:
        return []
    rows = await _get(f"/internal/assets/{asset_type}/{kind}", {"code": codes})
    return [MarketRowSchema.model_validate(r) for r in rows]


# --------------------------------------------------------------------------- #
# Crawl control — mirrors run_crawl / sync_catalog / the scheduler half of
# crawl_status
# --------------------------------------------------------------------------- #
async def trigger_crawl(
    *,
    kind: CrawlKind,
    codes_by_type: dict[str, list[str]] | None = None,
    trigger: CrawlTrigger = CrawlTrigger.MANUAL,
    portfolio_id: int | None = None,
    dedup: bool = True,
) -> CrawlTriggerResponse:
    body = CrawlRequest(
        kind=kind,
        codes_by_type=codes_by_type,
        trigger=trigger,
        portfolio_id=portfolio_id,
        dedup=dedup,
    )
    data = await _request("POST", "/internal/crawl", json=body.model_dump(mode="json"))
    return CrawlTriggerResponse.model_validate(data)


async def sync_catalog() -> CrawlTriggerResponse:
    data = await _request("POST", "/internal/catalog/sync")
    return CrawlTriggerResponse.model_validate(data)


async def scheduler_status() -> CrawlStatusSchema:
    data = await _get("/internal/scheduler/status")
    return CrawlStatusSchema.model_validate(data)
