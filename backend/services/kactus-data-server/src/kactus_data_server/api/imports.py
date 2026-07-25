"""``POST /internal/gold/import`` — one-shot historical CSV ingestion.

The only endpoint that accepts data *into* the data plane. The body is the raw
CSV (``text/csv``), not multipart: the control plane already holds the bytes,
and re-wrapping them in a form just to unwrap them here would add a parser and
a dependency for nothing. Format detection (SJC / XAU / PNJ) happens beside
the table definition in ``kactus_data.sources.gold.history``.

Synchronous on purpose, unlike ``/internal/crawl``: the caller is a user
watching an upload dialog, and the whole parse + upsert of the largest file
(~92k rows) is a few seconds — a status code now beats a job id to poll.
"""

from __future__ import annotations

import asyncio

from fastapi import Depends, Request
from kactus_common.market.schema import GoldImportResultSchema
from kactus_common.router import KactusAPIRouter
from kactus_data.sources.gold.history import import_history
from kactus_data_server.runtime import get_runtime
from kactus_data_server.security import require_service_token

router = KactusAPIRouter(
    prefix="/internal",
    tags=["internal-imports"],
    dependencies=[Depends(require_service_token)],
)


@router.post("/gold/import")
async def import_gold_history(
    request: Request, filename: str | None = None
) -> GoldImportResultSchema:
    """Parse one gold-history CSV and upsert it into ``gold_price_history``."""
    content = await request.body()
    return await asyncio.to_thread(
        import_history, get_runtime().storage, content, filename
    )
