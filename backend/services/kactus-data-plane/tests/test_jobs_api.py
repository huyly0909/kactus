"""``/internal/crawl``, ``/internal/catalog/sync``, ``/internal/scheduler/status``.

Commands, deliberately over HTTP rather than fire-and-forget: the caller wants
to know whether the ask was accepted or deduped. A trigger *enqueues* a
``SyncJob`` (the PENDING ack) that the data-plane dispatcher executes FIFO —
these tests pin down the enqueue/dedup contract, not the execution (that lives
in kactus-data's crawl-handler tests).
"""

from __future__ import annotations

import pytest
from kactus_common.sync.const import SyncJobStatus
from kactus_common.sync.model import SyncJob
from kactus_data.jobs.scheduler import build_scheduler
from kactus_data_plane.runtime import get_runtime
from sqlalchemy import select


async def _all_jobs(db) -> list[SyncJob]:
    async with db.get_session() as session:
        return list((await session.scalars(select(SyncJob))).all())


@pytest.mark.asyncio
async def test_crawl_is_accepted_and_enqueued(client, db):
    """The response acks with job ids; the PENDING rows prove the enqueue."""
    resp = await client.post(
        "/internal/crawl",
        json={"kind": "quotes", "codes_by_type": {"STOCK": ["FPT"]}},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["skipped"] is False
    assert len(data["job_ids"]) == 1

    jobs = await _all_jobs(db)
    assert [j.job_type for j in jobs] == ["stock_quotes"]
    assert jobs[0].status == str(SyncJobStatus.PENDING)
    assert jobs[0].params["codes"] == ["FPT"]


@pytest.mark.asyncio
async def test_dedup_skips_an_inflight_crawl(client, db):
    """The active-unique ``dedup_key`` lives in Postgres, so it holds across
    both planes — a scheduled crawl and a user-pressed refresh cannot both burn
    the vnstock budget on the same dataset."""
    body = {"kind": "quotes", "codes_by_type": {"STOCK": ["FPT"]}}
    first = (await client.post("/internal/crawl", json=body)).json()["data"]
    second = (await client.post("/internal/crawl", json=body)).json()["data"]

    assert first["skipped"] is False
    assert second["skipped"] is True
    assert "already queued" in second["message"]
    assert len(await _all_jobs(db)) == 1  # no duplicate row was stacked


@pytest.mark.asyncio
async def test_crawl_defaults_to_the_watchlist_union(client, db):
    """Omitting ``codes_by_type`` defers symbol selection to the handler.

    The job is enqueued with ``codes=None`` so the dispatcher resolves the
    *live* watchlist union at run time, not a snapshot from trigger time.
    """
    resp = await client.post("/internal/crawl", json={"kind": "quotes"})
    data = resp.json()["data"]
    assert data["skipped"] is False
    # quotes fans out to both asset families when no codes narrow it.
    assert len(data["job_ids"]) == 2

    jobs = await _all_jobs(db)
    assert {j.job_type for j in jobs} == {"stock_quotes", "gold_quotes"}
    assert all(j.params["codes"] is None for j in jobs)


@pytest.mark.asyncio
async def test_crawl_rejects_an_unknown_kind(client):
    resp = await client.post("/internal/crawl", json={"kind": "nonsense"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_catalog_sync_is_accepted_and_dedups(client, db):
    resp = await client.post("/internal/catalog/sync")
    assert resp.status_code == 200
    assert resp.json()["data"]["skipped"] is False

    again = (await client.post("/internal/catalog/sync")).json()["data"]
    assert again["skipped"] is True

    jobs = await _all_jobs(db)
    assert [j.job_type for j in jobs] == ["catalog_sync"]


@pytest.mark.asyncio
async def test_scheduler_status_with_scheduler_off(client, monkeypatch):
    """The fixture runs no scheduler, which is also the read-only deployment."""
    # Tier detection asks vnai (works even unauthenticated now) — pin it so the
    # test does not depend on the machine's vnai cache/network.
    monkeypatch.setattr("kactus_data_plane.api.jobs._safe_tier_name", lambda: "free")
    data = (await client.get("/internal/scheduler/status")).json()["data"]
    assert data["scheduler_running"] is False
    assert data["jobs"] == []
    assert data["vnstock_tier"] == "free"


@pytest.mark.asyncio
async def test_scheduler_status_reports_names_and_cron_fields(client, db, monkeypatch):
    """Every job is named and its cadence ships structured, in a stated zone.

    Without ``name=`` APScheduler derives one from the callable and five of the
    six jobs read ``build_scheduler.<locals>._crawl``; without ``cron`` the
    client is left parsing ``str(trigger)``. Both are what the admin table
    shows, so both are pinned here.
    """
    monkeypatch.setattr("kactus_data_plane.api.jobs._safe_tier_name", lambda: "free")
    monkeypatch.setattr(get_runtime(), "scheduler", build_scheduler(db=db))

    jobs = {
        j["id"]: j
        for j in (await client.get("/internal/scheduler/status")).json()["data"]["jobs"]
    }
    assert set(jobs) == {
        "crawl_quotes",
        "crawl_news",
        "crawl_ratios",
        "crawl_events",
        "crawl_ohlcv",
        "sync_catalog",
    }
    assert all("<locals>" not in j["name"] for j in jobs.values())
    assert jobs["crawl_quotes"]["name"] == "Crawl quotes"
    assert jobs["crawl_quotes"]["cron"] == {
        "day_of_week": "mon-fri",
        "hour": "9-15",
        "minute": "0",
    }
    # The catalog is the one job with no day_of_week — it runs weekends too, and
    # that absence is what the UI turns into "Daily".
    assert jobs["sync_catalog"]["cron"] == {"hour": "8", "minute": "30"}
    assert jobs["sync_catalog"]["timezone"] == "Asia/Ho_Chi_Minh"
