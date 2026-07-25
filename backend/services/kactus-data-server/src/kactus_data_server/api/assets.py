"""``/internal/assets/*`` — the ``provider.read(kind, codes)`` seam, over HTTP.

One endpoint replaces all three call sites that used to reach into the provider
registry from kactus-fin (portfolio quotes, portfolio news, asset detail). They
differ only in how the control plane *projects* the rows afterwards, which is
presentation and stays there.

Rows cross the wire as ``MarketRowSchema`` — an opaque dict keyed by the
dataset's own columns, because the shape varies per kind and per vnstock source
and pinning it here would mean a schema change every time a source adds a
column.
"""

from __future__ import annotations

import asyncio
import math
from decimal import Decimal

import pandas as pd
from fastapi import Depends, Query
from kactus_common.portfolio.const import AssetType, CrawlKind
from kactus_common.portfolio.schema import MarketRowSchema
from kactus_common.router import KactusAPIRouter
from kactus_common.schemas import decimal_to_str
from kactus_data_server.runtime import get_runtime
from kactus_data_server.security import require_service_token

router = KactusAPIRouter(
    prefix="/internal/assets",
    tags=["internal-assets"],
    dependencies=[Depends(require_service_token)],
)

#: The verbatim source payload. Every consumer either reads named columns or
#: strips this, so it is dropped at the source rather than shipped — for a
#: 30-symbol watchlist it is the bulk of the response and none of the meaning.
_DROPPED_COLUMNS = frozenset({"raw_json"})


@router.get("/{asset_type}/{kind}")
async def read_asset_rows(
    asset_type: AssetType,
    kind: CrawlKind,
    code: list[str] = Query(default=[]),
) -> list[MarketRowSchema]:
    """Stored ``kind`` rows for ``code``, straight from DuckDB.

    An asset type with no provider, or a kind that provider does not produce,
    is an empty list — not an error. The control plane asks for every kind a
    portfolio might contain and lets the gaps fall away.
    """
    provider = get_runtime().providers.get(asset_type)
    if provider is None or kind not in provider.supported_kinds():
        return []

    codes = [c.upper() for c in code]
    rows = await asyncio.to_thread(provider.read, kind, codes)
    return [
        MarketRowSchema(
            symbol=r.get("symbol") or r.get("code"),
            data={k: _jsonable(v) for k, v in r.items() if k not in _DROPPED_COLUMNS},
        )
        for r in rows
    ]


def _jsonable(value: object) -> object:
    """Normalise a DuckDB cell so it survives JSON and comes back the same.

    Money columns are DECIMAL, so they arrive as ``Decimal``. Inside an ``Any``
    field Pydantic would emit those as JSON *strings* while floats stay bare
    numbers — an inconsistent shape for one row. Render them as strings
    explicitly, matching how ``FancyDecimal`` serialises the typed routes.

    NaN/NaT mean "missing" in a DataFrame but are not JSON: a literal ``NaN``
    token is accepted by Python's parser and rejected by most others, so it
    would work right up until something other than this codebase read the
    response. Normalise to null, as ``MarketService`` already does for the
    market tables.
    """
    if isinstance(value, Decimal):
        # A NaN Decimal is still a Decimal — check before stringifying it.
        return None if value.is_nan() else decimal_to_str(value)
    # Identity, not ``pd.isna``: that returns an *array* for array-valued cells
    # and the truth test on it raises. numpy's float64 subclasses float, so the
    # isnan branch covers it too.
    if value is pd.NaT:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value
