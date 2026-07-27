"""Tests for the shared sync-job queue service.

In-memory SQLite (aiosqlite). Exercises enqueue dedup (incl. the partial unique
index that only blocks *live* duplicates), FIFO claim, progress persistence,
orphan requeue (resume), and cancel.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.sync.const import SyncJobStatus
from kactus_common.sync.service import SyncJobService

TEST_DB_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def db():
    manager = DatabaseSessionManager(database_url=TEST_DB_URL)
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield manager
    async with manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await manager.close()


# Any wire string works — the queue is domain-agnostic (gold just got here first).
async def _enqueue(session, key="gold_backfill:sjc", type_="gold_backfill"):
    return await SyncJobService.enqueue(
        session, job_type=type_, params={"source": "sjc"}, dedup_key=key
    )


@pytest.mark.asyncio
async def test_enqueue_creates_pending(db):
    async with db.get_session() as session:
        job, created = await _enqueue(session)
        assert created is True
        assert job.status == SyncJobStatus.PENDING
        assert job.progress_pct == 0


@pytest.mark.asyncio
async def test_enqueue_dedups_live_job(db):
    """A second enqueue with the same key returns the live job, not a new one."""
    async with db.get_session() as session:
        first, c1 = await _enqueue(session)
        second, c2 = await _enqueue(session)
        assert c1 is True and c2 is False
        assert first.id == second.id
        assert await SyncJobService.active_keys(session) == {"gold_backfill:sjc"}


@pytest.mark.asyncio
async def test_finished_job_frees_dedup_key(db):
    """The partial index only blocks *live* dupes — a finished key re-enqueues."""
    async with db.get_session() as session:
        first, _ = await _enqueue(session)
        claimed = await SyncJobService.claim_next(session)
        await SyncJobService.finish(session, claimed, status=SyncJobStatus.SUCCESS)

        second, created = await _enqueue(session)
        assert created is True
        assert second.id != first.id


@pytest.mark.asyncio
async def test_claim_is_fifo(db):
    async with db.get_session() as session:
        a, _ = await _enqueue(session, key="gold_backfill:sjc")
        b, _ = await _enqueue(session, key="gold_backfill:yahoo")
        first = await SyncJobService.claim_next(session)
        second = await SyncJobService.claim_next(session)
        assert [first.id, second.id] == [a.id, b.id]
        assert first.status == SyncJobStatus.RUNNING
        assert first.started_at is not None


@pytest.mark.asyncio
async def test_progress_and_finish(db):
    async with db.get_session() as session:
        await _enqueue(session)
        job = await SyncJobService.claim_next(session)
        await SyncJobService.update_progress(
            session, job, done=3, total=10, cursor="2020-01-01"
        )
        assert job.progress_pct == 30
        assert job.cursor == "2020-01-01"
        await SyncJobService.finish(
            session, job, status=SyncJobStatus.SUCCESS, result={"rows": 42}
        )
        assert job.status == SyncJobStatus.SUCCESS
        assert job.finished_at is not None
        assert job.result == {"rows": 42}


@pytest.mark.asyncio
async def test_requeue_orphans_preserves_progress(db):
    """A crashed RUNNING job returns to PENDING keeping progress + cursor."""
    async with db.get_session() as session:
        await _enqueue(session)
        job = await SyncJobService.claim_next(session)
        await SyncJobService.update_progress(
            session, job, done=5, total=10, cursor="w5"
        )

        n = await SyncJobService.requeue_orphans(session)
        assert n == 1

        resumed = await SyncJobService.claim_next(session)
        assert resumed.id == job.id
        assert resumed.progress_done == 5
        assert resumed.cursor == "w5"


@pytest.mark.asyncio
async def test_cancel_running_job(db):
    async with db.get_session() as session:
        await _enqueue(session)
        job = await SyncJobService.claim_next(session)
        assert await SyncJobService.is_cancelled(session, job.id) is False
        cancelled = await SyncJobService.cancel(session, job.id)
        assert cancelled.status == SyncJobStatus.CANCELLED
        assert await SyncJobService.is_cancelled(session, job.id) is True
        # After cancel, the dedup key is free again.
        _, created = await _enqueue(session)
        assert created is True
