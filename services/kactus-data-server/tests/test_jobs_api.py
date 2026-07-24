"""``/internal/crawl``, ``/internal/catalog/sync``, ``/internal/scheduler/status``.

Commands, deliberately over HTTP rather than a queue: the caller wants to know
whether the ask was accepted, and a status code is the cheapest way to say so.
The work itself runs in a background task, so acceptance and completion are two
different things — these tests pin down the first.
"""

from __future__ import annotations

import pytest
from kactus_common.portfolio.const import AssetType, CrawlKind
from kactus_common.portfolio.service import CrawlRunService


@pytest.mark.asyncio
async def test_crawl_is_accepted_and_runs(client, db):
    """The response says 'scheduled'; the CrawlRun row proves it ran."""
    resp = await client.post(
        "/internal/crawl",
        json={"kind": "quotes", "codes_by_type": {"STOCK": ["FPT"]}, "dedup": True},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["skipped"] is False

    # ASGITransport runs BackgroundTasks before the response context exits, so
    # by the time we are here the crawl has completed.
    async with db.get_session() as session:
        runs = await CrawlRunService.list_recent(session, limit=10)
    assert [r.kind for r in runs] == [CrawlKind.QUOTES]
    assert runs[0].asset_type == AssetType.STOCK


@pytest.mark.asyncio
async def test_dedup_skips_an_inflight_crawl(client, db):
    """The in-flight marker lives in Postgres, so it holds across both planes.

    This is the guard that keeps a scheduled crawl and a user-pressed refresh
    from both burning the vnstock rate-limit budget on the same symbols.
    """
    async with db.get_session() as session:
        await CrawlRunService.start(
            session, asset_type=AssetType.STOCK, kind=CrawlKind.QUOTES
        )

    await client.post(
        "/internal/crawl",
        json={"kind": "quotes", "codes_by_type": {"STOCK": ["FPT"]}, "dedup": True},
    )

    async with db.get_session() as session:
        runs = await CrawlRunService.list_recent(session, limit=10)
    # Still only the pre-seeded in-flight run — no second one was started.
    assert len(runs) == 1


@pytest.mark.asyncio
async def test_crawl_defaults_to_the_watchlist_union(client, db):
    """Omitting ``codes_by_type`` hands symbol selection to the data plane.

    That is what the scheduler does, and what an operator hitting the endpoint
    by hand almost always means — the control plane should not have to
    enumerate every user's watchlist to ask for a refresh.
    """
    from kactus_common.portfolio.service import SupportedAssetService

    async with db.get_session() as session:
        await SupportedAssetService.upsert_many(
            session,
            asset_type=AssetType.STOCK,
            entries=[{"code": "FPT", "name": "FPT", "tags": ["VN30"]}],
        )

    resp = await client.post("/internal/crawl", json={"kind": "quotes"})
    assert resp.json()["data"]["skipped"] is False

    async with db.get_session() as session:
        runs = await CrawlRunService.list_recent(session, limit=10)
    assert len(runs) == 1


@pytest.mark.asyncio
async def test_crawl_rejects_an_unknown_kind(client):
    resp = await client.post("/internal/crawl", json={"kind": "nonsense"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_catalog_sync_is_accepted(client):
    resp = await client.post("/internal/catalog/sync")
    assert resp.status_code == 200
    assert resp.json()["data"]["skipped"] is False


@pytest.mark.asyncio
async def test_scheduler_status_with_scheduler_off(client):
    """The fixture runs no scheduler, which is also the read-only deployment."""
    data = (await client.get("/internal/scheduler/status")).json()["data"]
    assert data["scheduler_running"] is False
    assert data["jobs"] == []
    # The tier is the vnstock key's property, not the scheduler's, and is null
    # until `init_vnstock_auth` has run — which it has not here, and would not
    # in a read-only deployment either.
    assert data["vnstock_tier"] is None
