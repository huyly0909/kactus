"""Tests for the sync-job dispatcher loop.

Drives the dispatcher with fake handlers (no DuckDB / no network) against
in-memory SQLite, covering: a job run to SUCCESS with progress persisted at
100%, a handler raising → FAILED, an unknown job type → FAILED, mid-run cancel
raising ``SyncJobCancelled`` at the next checkpoint, and the full
``run_dispatcher`` loop claiming + finishing one enqueued job then stopping.

The SSE broker is the in-process default (no subscribers), so ``_publish`` is a
harmless no-op here.
"""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from kactus_common.database.oltp.models import Base
from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.sync.const import SyncJobStatus, SyncJobType
from kactus_common.sync.model import SyncJob
from kactus_common.sync.service import SyncJobService
from kactus_data.jobs import sync_queue
from kactus_data.jobs.sync_queue import (
    SYNC_HANDLERS,
    SyncJobCancelled,
    SyncJobDeps,
    run_dispatcher,
)

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


@pytest.fixture(autouse=True)
def _isolate_handlers():
    """Snapshot/restore the module-global handler registry around each test."""
    saved = dict(SYNC_HANDLERS)
    SYNC_HANDLERS.clear()
    yield
    SYNC_HANDLERS.clear()
    SYNC_HANDLERS.update(saved)


async def _enqueue_and_claim(db, *, job_type=SyncJobType.GOLD_BACKFILL, key="k"):
    async with db.get_session() as session:
        await SyncJobService.enqueue(
            session, job_type=job_type, params={"source": "sjc"}, dedup_key=key
        )
        job = await SyncJobService.claim_next(session)
        return sync_queue._view(job), job.id


async def _reload(db, job_id):
    async with db.get_session() as session:
        return await SyncJob.get(session, job_id)


@pytest.mark.asyncio
async def test_run_job_success_persists_full_progress(db):
    async def handler(view, deps, on_progress):
        await on_progress(1, 3, cursor="w1")
        return {"total": 3, "rows": 10}

    SYNC_HANDLERS[str(SyncJobType.GOLD_BACKFILL)] = handler
    view, job_id = await _enqueue_and_claim(db)

    deps = SyncJobDeps(db=db, storage=None, providers={})
    await sync_queue._run_job(deps, view)

    job = await _reload(db, job_id)
    assert job.status == str(SyncJobStatus.SUCCESS)
    assert job.result == {"total": 3, "rows": 10}
    # finish() bumps progress to total, so a done job reads as 100%.
    assert job.progress_done == 3
    assert job.progress_total == 3
    assert job.progress_pct == 100
    assert job.finished_at is not None


@pytest.mark.asyncio
async def test_run_job_handler_error_marks_failed(db):
    async def handler(view, deps, on_progress):
        raise RuntimeError("boom")

    SYNC_HANDLERS[str(SyncJobType.GOLD_BACKFILL)] = handler
    view, job_id = await _enqueue_and_claim(db)

    deps = SyncJobDeps(db=db, storage=None, providers={})
    await sync_queue._run_job(deps, view)

    job = await _reload(db, job_id)
    assert job.status == str(SyncJobStatus.FAILED)
    assert "boom" in job.message


@pytest.mark.asyncio
async def test_run_job_unknown_type_marks_failed(db):
    view, job_id = await _enqueue_and_claim(db)  # no handler registered

    deps = SyncJobDeps(db=db, storage=None, providers={})
    await sync_queue._run_job(deps, view)

    job = await _reload(db, job_id)
    assert job.status == str(SyncJobStatus.FAILED)
    assert "No handler" in job.message


@pytest.mark.asyncio
async def test_cancel_stops_at_next_checkpoint(db):
    """Cancelling mid-run makes the next on_progress raise; job stays CANCELLED."""
    chunks_done = []

    async def handler(view, deps, on_progress):
        await on_progress(1, 3)  # first checkpoint ok
        chunks_done.append(1)
        # Cancel between chunks (as the API's cancel endpoint would).
        async with deps.db.get_session() as session:
            await SyncJobService.cancel(session, view.id)
        await on_progress(2, 3)  # must raise SyncJobCancelled
        chunks_done.append(2)  # unreachable

    SYNC_HANDLERS[str(SyncJobType.GOLD_BACKFILL)] = handler
    view, job_id = await _enqueue_and_claim(db)

    deps = SyncJobDeps(db=db, storage=None, providers={})
    await sync_queue._run_job(deps, view)  # swallows SyncJobCancelled

    assert chunks_done == [1]
    job = await _reload(db, job_id)
    assert job.status == str(SyncJobStatus.CANCELLED)


@pytest.mark.asyncio
async def test_on_progress_raises_when_cancelled(db):
    """The checkpoint callback itself raises SyncJobCancelled on a cancelled job."""
    view, job_id = await _enqueue_and_claim(db)
    deps = SyncJobDeps(db=db, storage=None, providers={})
    on_progress = sync_queue._make_on_progress(deps, view)

    await on_progress(1, 2)  # fine while running
    async with db.get_session() as session:
        await SyncJobService.cancel(session, job_id)
    with pytest.raises(SyncJobCancelled):
        await on_progress(2, 2)


@pytest.mark.asyncio
async def test_dispatcher_loop_claims_and_finishes(db):
    ran = []

    async def handler(view, deps, on_progress):
        await on_progress(1, 1)
        ran.append(view.id)
        return {"total": 1}

    SYNC_HANDLERS[str(SyncJobType.GOLD_SYNC)] = handler
    async with db.get_session() as session:
        job, _ = await SyncJobService.enqueue(
            session,
            job_type=SyncJobType.GOLD_SYNC,
            params={},
            dedup_key="gold_sync:all",
        )
        job_id = job.id

    deps = SyncJobDeps(db=db, storage=None, providers={})
    stop = asyncio.Event()
    task = asyncio.create_task(
        run_dispatcher(deps, poll_interval=0.01, stop_event=stop)
    )

    for _ in range(200):
        await asyncio.sleep(0.01)
        job = await _reload(db, job_id)
        if job.status == str(SyncJobStatus.SUCCESS):
            break

    stop.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert ran == [job_id]
    job = await _reload(db, job_id)
    assert job.status == str(SyncJobStatus.SUCCESS)


@pytest.mark.asyncio
async def test_dispatcher_requeues_orphans_on_boot(db):
    """A RUNNING job left by a crash is resumed by the loop, not stranded."""
    ran = []

    async def handler(view, deps, on_progress):
        ran.append((view.id, view.progress_done, view.cursor))
        return {"total": view.progress_total}

    SYNC_HANDLERS[str(SyncJobType.GOLD_BACKFILL)] = handler
    # Simulate a crash: claim + progress, but never finish (status stays RUNNING).
    async with db.get_session() as session:
        await SyncJobService.enqueue(
            session, job_type=SyncJobType.GOLD_BACKFILL, params={}, dedup_key="k"
        )
        job = await SyncJobService.claim_next(session)
        await SyncJobService.update_progress(
            session, job, done=4, total=10, cursor="w4"
        )
        job_id = job.id

    deps = SyncJobDeps(db=db, storage=None, providers={})
    stop = asyncio.Event()
    task = asyncio.create_task(
        run_dispatcher(deps, poll_interval=0.01, stop_event=stop)
    )

    for _ in range(200):
        await asyncio.sleep(0.01)
        job = await _reload(db, job_id)
        if job.status == str(SyncJobStatus.SUCCESS):
            break

    stop.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Resumed with its saved cursor/progress, not restarted from zero.
    assert ran == [(job_id, 4, "w4")]
