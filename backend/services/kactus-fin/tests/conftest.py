"""Shared fixtures for the kactus-fin tests.

The interesting one is ``data_plane``: a stand-in for kactus-data-plane, served
to ``data_client`` through an in-process ASGI transport.

Why a fake *server* rather than monkeypatching the client functions — the client
is now the thing most likely to break. Query-parameter names, the ``ResponseModel``
envelope, Decimal-as-string round-tripping, the error mapping: all of that is
real code that a stubbed ``data_client.list_gold`` would skip straight past.
Routing it through a real httpx client against a real FastAPI app exercises
every layer except the socket.

The fake declares the same routes as ``kactus_data_plane.api`` but cannot
import it: kactus-fin has no dependency on the data plane, and the import-linter
contract forbids adding one. The duplication is the point — if the two drift,
these tests keep passing while production breaks, which is why the data plane
has its own contract tests against the same schemas.
"""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, Query, Request
from httpx import ASGITransport
from kactus_common.exceptions import install_exception_handlers
from kactus_common.portfolio.schema import (
    CrawlJobSchema,
    CrawlRequest,
    CrawlStatusSchema,
    CrawlTriggerResponse,
    MarketRowSchema,
)
from kactus_common.router import KactusAPIRouter
from kactus_gold.schema import (
    GoldHistoryCodeSchema,
    GoldHistoryPointSchema,
    GoldImportResultSchema,
    GoldPriceSchema,
)
from kactus_stock_vn.schema import (
    FinanceReportSchema,
    OHLCVSchema,
    StockDetailSchema,
    StockListingSchema,
    StockNewsSchema,
    StockQuoteSchema,
)


class FakeDataPlane:
    """Canned responses, plus a log of what the client actually asked for."""

    def __init__(self) -> None:
        self.gold: list[GoldPriceSchema] = []
        self.gold_history: list[GoldHistoryPointSchema] = []
        self.gold_history_codes: list[GoldHistoryCodeSchema] = []
        self.import_result: GoldImportResultSchema | None = None
        #: raw bodies received by /internal/gold/import, in call order
        self.import_bodies: list[bytes] = []
        self.listings: list[StockListingSchema] = []
        self.quotes: list[StockQuoteSchema] = []
        self.detail: StockDetailSchema | None = None
        self.ohlcv: list[OHLCVSchema] = []
        self.news: list[StockNewsSchema] = []
        self.finance: list[FinanceReportSchema] = []
        #: (asset_type, kind) -> rows
        self.asset_rows: dict[tuple[str, str], list[MarketRowSchema]] = {}
        self.calls: list[tuple[str, dict]] = []

    def build_app(self) -> FastAPI:
        fake = self
        router = KactusAPIRouter(prefix="/internal")

        @router.get("/market/gold")
        async def gold(code: list[str] | None = Query(default=None)):
            fake.calls.append(("gold", {"code": code}))
            return fake.gold

        @router.get("/market/gold/history")
        async def gold_history(
            code: str,
            start: str | None = None,
            end: str | None = None,
            limit: int = 2500,
        ):
            fake.calls.append(
                (
                    "gold_history",
                    {"code": code, "start": start, "end": end, "limit": limit},
                )
            )
            return fake.gold_history

        @router.get("/market/gold/history/codes")
        async def gold_history_codes():
            fake.calls.append(("gold_history_codes", {}))
            return fake.gold_history_codes

        @router.post("/gold/import")
        async def gold_import(
            request: Request, filename: str | None = None
        ) -> GoldImportResultSchema:
            body = await request.body()
            fake.import_bodies.append(body)
            fake.calls.append(
                ("gold_import", {"filename": filename, "size": len(body)})
            )
            return fake.import_result or GoldImportResultSchema(
                dataset="sjc",
                filename=filename,
                rows_parsed=len(body),
                rows_imported=0,
                rows_skipped=0,
                codes=0,
            )

        @router.get("/market/stocks")
        async def stocks(q: str | None = None, limit: int = 50):
            fake.calls.append(("stocks", {"q": q, "limit": limit}))
            return fake.listings

        @router.get("/market/stocks/quotes")
        async def quotes(
            symbol: list[str] | None = Query(default=None), limit: int = 50
        ):
            fake.calls.append(("quotes", {"symbol": symbol, "limit": limit}))
            return fake.quotes

        @router.get("/market/stocks/{symbol}")
        async def detail(symbol: str) -> StockDetailSchema | None:
            fake.calls.append(("detail", {"symbol": symbol}))
            return fake.detail

        @router.get("/market/stocks/{symbol}/ohlcv")
        async def ohlcv(
            symbol: str,
            interval: str = "1D",
            start: str | None = None,
            end: str | None = None,
            limit: int = 500,
        ):
            fake.calls.append(
                ("ohlcv", {"symbol": symbol, "interval": interval, "limit": limit})
            )
            return fake.ohlcv

        @router.get("/market/stocks/{symbol}/news")
        async def news(symbol: str, limit: int = 20):
            fake.calls.append(("news", {"symbol": symbol, "limit": limit}))
            return fake.news

        @router.get("/market/stocks/{symbol}/finance")
        async def finance(
            symbol: str,
            report_type: str = "income_statement",
            period: str | None = None,
            limit: int = 20,
        ):
            fake.calls.append(
                ("finance", {"symbol": symbol, "report_type": report_type})
            )
            return fake.finance

        @router.get("/assets/{asset_type}/{kind}")
        async def assets(
            asset_type: str, kind: str, code: list[str] = Query(default=[])
        ) -> list[MarketRowSchema]:
            fake.calls.append(
                ("assets", {"asset_type": asset_type, "kind": kind, "code": code})
            )
            return fake.asset_rows.get((asset_type, kind), [])

        @router.post("/crawl")
        async def crawl(body: CrawlRequest) -> CrawlTriggerResponse:
            fake.calls.append(("crawl", body.model_dump(mode="json")))
            return CrawlTriggerResponse(skipped=False, message="Crawl scheduled")

        @router.post("/catalog/sync")
        async def catalog_sync() -> CrawlTriggerResponse:
            fake.calls.append(("catalog_sync", {}))
            return CrawlTriggerResponse(skipped=False, message="Catalog sync scheduled")

        @router.get("/scheduler/status")
        async def status() -> CrawlStatusSchema:
            fake.calls.append(("status", {}))
            return CrawlStatusSchema(
                scheduler_running=True,
                vnstock_tier="guest",
                jobs=[CrawlJobSchema(id="crawl_quotes", next_run_time=None)],
            )

        app = FastAPI()
        install_exception_handlers(app)
        app.include_router(router)
        return app

    def last(self, name: str) -> dict:
        """Params of the most recent call to *name* (KeyError-loud if never)."""
        for call_name, params in reversed(self.calls):
            if call_name == name:
                return params
        raise AssertionError(f"data plane was never asked for {name!r}")


@pytest.fixture
def data_plane() -> FakeDataPlane:
    return FakeDataPlane()


@pytest_asyncio.fixture(autouse=True)
async def wire_data_plane(data_plane):
    """Point ``data_client`` at the fake for every test in this package.

    Autouse and unconditional: without it a test that accidentally hits the
    market path would try to open a real socket to localhost:17602 and fail
    slowly and confusingly instead of at the assertion.
    """
    from kactus_fin import data_client

    data_client.reset_client()
    data_client._client = httpx.AsyncClient(
        transport=ASGITransport(app=data_plane.build_app()),
        base_url="http://data-plane",
        headers={"X-Service-Token": "test-token"},
    )
    yield data_plane
    await data_client.close_client()
