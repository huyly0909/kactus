"""``/internal/market/*`` — the seven MarketService reads over HTTP.

Moved here from kactus-fin when the data plane took ownership of DuckDB. The
assertions are unchanged: the same seeded rows, the same derived values, the
same exact-decimal money. What changed is the caller — these now prove the
*data plane* returns them, and kactus-fin's suite proves it renders whatever it
is handed.

One deliberate difference from the old suite: an unknown symbol is ``null``
here, not a 404. The 404 is a product decision and lives in the control plane.
"""

from __future__ import annotations

import pytest
from kactus_data.storage.duckdb import DuckDBStorage


@pytest.mark.asyncio
async def test_gold_board_and_filter(client):
    resp = await client.get("/internal/market/gold")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "0"
    rows = body["data"]
    assert {r["code"] for r in rows} == {"999", "SJC", "XAU"}

    sjc = next(r for r in rows if r["code"] == "SJC")
    # spread is derived, not stored
    assert float(sjc["spread"]) == pytest.approx(2_000_000.0)

    filtered = await client.get("/internal/market/gold", params={"code": "SJC"})
    assert [r["code"] for r in filtered.json()["data"]] == ["SJC"]


@pytest.mark.asyncio
async def test_gold_prices_are_exact_and_unit_tagged(client):
    """Money survives the round trip as an exact decimal string, not a float.

    Domestic gold (~1.2e8 VND) is past float32's exact range and lands on
    binary fractions in float64, so the board stores DECIMAL and the API
    serialises it as a string.  ``unit`` is what tells VND/lượng apart from
    the USD/oz world price on the same board.

    This matters more after the split than before: the value now crosses a
    JSON boundary twice, and a float round-trip would round somewhere in the
    middle where nothing is watching.
    """
    rows = (await client.get("/internal/market/gold")).json()["data"]
    by_code = {r["code"]: r for r in rows}

    assert by_code["SJC"]["buy_price"] == "121000000"
    assert by_code["SJC"]["spread"] == "2000000"
    assert by_code["SJC"]["unit"] == "VND/luong"

    # World gold shares the board but is quoted per troy ounce in USD.
    assert by_code["XAU"]["unit"] == "USD/oz"
    assert by_code["XAU"]["buy_price"] == "4037.6999"


@pytest.mark.asyncio
async def test_stock_search_by_symbol_and_name(client):
    all_rows = await client.get("/internal/market/stocks")
    assert [r["symbol"] for r in all_rows.json()["data"]] == ["FPT", "VNM"]

    by_symbol = await client.get("/internal/market/stocks", params={"q": "fpt"})
    assert [r["symbol"] for r in by_symbol.json()["data"]] == ["FPT"]

    by_name = await client.get("/internal/market/stocks", params={"q": "vinamilk"})
    assert [r["symbol"] for r in by_name.json()["data"]] == ["VNM"]


@pytest.mark.asyncio
async def test_stock_detail_merges_company_and_quote(client):
    resp = await client.get("/internal/market/stocks/fpt")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "FPT"
    assert data["organ_name"] == "FPT Corp"
    assert data["company"]["industry"] == "Technology"
    # change/change_pct derived from match vs ref
    assert float(data["quote"]["change"]) == pytest.approx(10.0)
    assert float(data["quote"]["change_pct"]) == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_unknown_symbol_is_null_not_404(client):
    """The data plane reports absence; the control plane decides it's a 404.

    Keeping the 404 out of here means the user-facing message has exactly one
    home, and a genuinely mistyped *route* stays distinguishable from a symbol
    that simply was never crawled.
    """
    resp = await client.get("/internal/market/stocks/NOPE")
    assert resp.status_code == 200
    assert resp.json()["data"] is None


@pytest.mark.asyncio
async def test_quotes_board(client):
    resp = await client.get("/internal/market/stocks/quotes", params={"symbol": "fpt"})
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) == 1 and rows[0]["symbol"] == "FPT"


@pytest.mark.asyncio
async def test_quotes_route_is_not_shadowed_by_symbol_route(client):
    """``/stocks/quotes`` must not be read as ``/stocks/{symbol}``.

    Both are declared on the same router; only the declaration order keeps
    them apart. Reordering the module would silently turn every quotes call
    into a lookup for a stock named "quotes" — which returns null, so nothing
    would raise.
    """
    resp = await client.get("/internal/market/stocks/quotes")
    assert isinstance(resp.json()["data"], list)


@pytest.mark.asyncio
async def test_ohlcv_is_ascending_and_capped(client):
    resp = await client.get("/internal/market/stocks/FPT/ohlcv")
    assert resp.status_code == 200
    rows = resp.json()["data"]
    # API returns only the canonical UTC ``event_dt``; the seeded 15:00 VN bars
    # are 08:00 UTC, so the calendar day is unchanged by the conversion.
    assert [r["event_dt"][:10] for r in rows] == [
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
    ]

    # limit keeps the *newest* rows, still returned oldest → newest
    capped = await client.get("/internal/market/stocks/FPT/ohlcv", params={"limit": 2})
    assert [r["event_dt"][:10] for r in capped.json()["data"]] == [
        "2026-07-21",
        "2026-07-22",
    ]


@pytest.mark.asyncio
async def test_ohlcv_date_range_and_unknown_interval(client):
    ranged = await client.get(
        "/internal/market/stocks/FPT/ohlcv",
        params={"start": "2026-07-21", "end": "2026-07-21"},
    )
    assert [r["event_dt"][:10] for r in ranged.json()["data"]] == ["2026-07-21"]

    # an interval that was never crawled is empty, not an error
    empty = await client.get(
        "/internal/market/stocks/FPT/ohlcv", params={"interval": "1W"}
    )
    assert empty.json()["data"] == []

    # an interval outside the enum is rejected up front
    bad = await client.get(
        "/internal/market/stocks/FPT/ohlcv", params={"interval": "3Y"}
    )
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_news(client):
    resp = await client.get("/internal/market/stocks/FPT/news")
    rows = resp.json()["data"]
    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.test/n1"


@pytest.mark.asyncio
async def test_finance_reports_newest_first(client):
    resp = await client.get(
        "/internal/market/stocks/FPT/finance",
        params={"report_type": "income_statement", "period": "quarter"},
    )
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert [r["year"] for r in rows] == ["2026", "2025"]
    # data_json is exploded back into a dict
    assert rows[0]["data"]["revenue"] == 2026 * 1000

    # a report type with no crawled rows is empty, not an error
    empty = await client.get(
        "/internal/market/stocks/FPT/finance", params={"report_type": "cash_flow"}
    )
    assert empty.json()["data"] == []


@pytest.mark.asyncio
async def test_missing_tables_return_empty(client, tmp_path):
    """A DuckDB file with no ETL tables yet reads as 'no data', not a 500."""
    from kactus_data_server.runtime import get_runtime

    get_runtime().storage = DuckDBStorage(str(tmp_path / "empty.duckdb"))
    resp = await client.get("/internal/market/gold")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_runtime_not_initialised():
    from kactus_common.exceptions import InternalError
    from kactus_data_server.runtime import get_runtime, set_runtime

    set_runtime(None)
    with pytest.raises(InternalError):
        get_runtime()
