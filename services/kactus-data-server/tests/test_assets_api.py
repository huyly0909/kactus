"""``/internal/assets/{asset_type}/{kind}`` — the provider.read seam over HTTP.

Replaces three call sites that used to reach into the provider registry from
kactus-fin. The rows are opaque by design, so what these tests pin down is the
*envelope* around them: which columns are dropped, which cells are normalised,
and what an unsupported combination does.
"""

from __future__ import annotations

import math
from decimal import Decimal

import pandas as pd
import pytest
from kactus_common.portfolio.const import AssetType, CrawlKind
from kactus_data_server.api.assets import _jsonable


@pytest.fixture
def crawled(app):
    """Populate DuckDB through the fake provider, as a real crawl would."""
    from kactus_data_server.runtime import get_runtime

    provider = get_runtime().providers[AssetType.STOCK]
    provider.crawl(CrawlKind.QUOTES, ["FPT"])
    provider.crawl(CrawlKind.NEWS, ["FPT"])
    provider.crawl(CrawlKind.EVENTS, ["FPT"])
    return provider


@pytest.mark.asyncio
async def test_read_quotes(client, crawled):
    resp = await client.get("/internal/assets/STOCK/quotes", params={"code": "FPT"})
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) == 1
    assert rows[0]["symbol"] == "FPT"
    assert rows[0]["data"]["match_price"] == "25.5"


@pytest.mark.asyncio
async def test_code_is_upper_cased(client, crawled):
    """The control plane passes through whatever the user typed."""
    rows = (
        await client.get("/internal/assets/STOCK/quotes", params={"code": "fpt"})
    ).json()["data"]
    assert [r["symbol"] for r in rows] == ["FPT"]


@pytest.mark.asyncio
async def test_raw_json_never_crosses_the_wire(client, crawled):
    """The verbatim source payload is dropped at the source, not downstream.

    Every consumer either reads named columns or strips it; for a 30-symbol
    watchlist it is most of the bytes and none of the meaning.
    """
    rows = (
        await client.get("/internal/assets/STOCK/quotes", params={"code": "FPT"})
    ).json()["data"]
    assert "raw_json" not in rows[0]["data"]
    # …and the useful columns are still there.
    assert "ref_price" in rows[0]["data"]


@pytest.mark.asyncio
async def test_events_carry_their_own_columns(client, crawled):
    rows = (
        await client.get("/internal/assets/STOCK/events", params={"code": "FPT"})
    ).json()["data"]
    assert rows and rows[0]["data"]["title"] == "ĐHCĐ"


@pytest.mark.asyncio
async def test_unsupported_asset_type_is_empty_not_an_error(client, crawled):
    """GOLD has no provider in this fixture; the control plane asks anyway.

    A portfolio page asks for every kind it might contain and lets the gaps
    fall away — turning a gap into a 404 would break the page over an asset
    class the user does not even hold.
    """
    resp = await client.get("/internal/assets/GOLD/quotes", params={"code": "SJC"})
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_unsupported_kind_is_empty(client, crawled):
    """``foreign_trade`` is a real kind the STOCK provider does not produce.

    vnstock 4.x serves stocks via VCI, which has no foreign-flow endpoint, so
    the enum member is dormant rather than removed. Asking for it must read as
    "no data", the same as any other gap.
    """
    resp = await client.get(
        "/internal/assets/STOCK/foreign_trade", params={"code": "FPT"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_unknown_asset_type_is_rejected(client):
    """Outside the enum is a client bug, not an empty result."""
    resp = await client.get("/internal/assets/CRYPTO/quotes", params={"code": "BTC"})
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# _jsonable — the cell normaliser
# --------------------------------------------------------------------------- #
def test_jsonable_decimal_becomes_an_exact_string():
    """Money keeps every digit; a float here would round 1.21e8 quietly."""
    assert _jsonable(Decimal("121000000.00")) == "121000000"
    assert _jsonable(Decimal("4037.6999")) == "4037.6999"


def test_jsonable_missing_values_become_null():
    """NaN/NaT are DataFrame idioms, not JSON.

    A literal ``NaN`` token parses in Python and fails in most other parsers,
    so it would work right up until something outside this codebase read the
    response.
    """
    assert _jsonable(float("nan")) is None
    assert _jsonable(pd.NaT) is None
    assert _jsonable(Decimal("NaN")) is None


def test_jsonable_leaves_ordinary_values_alone():
    assert _jsonable("FPT") == "FPT"
    assert _jsonable(7) == 7
    assert _jsonable(None) is None
    assert _jsonable(1.5) == 1.5


def test_jsonable_does_not_truth_test_array_cells():
    """``pd.isna`` returns an *array* here and raises when tested for truth.

    The provider tables are DataFrame-shaped, so a list-valued cell (tags, a
    multi-value column added by a future vnstock version) is one schema change
    away — and it would 500 every asset read, not just its own row.
    """
    value = [1.0, float("nan")]
    assert _jsonable(value) == value


def test_jsonable_handles_numpy_floats():
    """numpy's float64 subclasses float, so the isnan branch must cover it."""
    import numpy as np

    assert _jsonable(np.float64("nan")) is None
    assert not math.isnan(_jsonable(np.float64(2.5)))
