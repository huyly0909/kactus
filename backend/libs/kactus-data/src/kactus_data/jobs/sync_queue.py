"""Sync-job dispatcher — the single FIFO executor for queued DuckDB writes.

DuckDB permits one writer, and the data plane is the one process holding it, so
one dispatcher drains the queue serially: claim the oldest PENDING job, run its
registered handler, persist progress after each chunk, finish. A restart resumes
in-flight work from the saved ``cursor`` (orphaned RUNNING jobs are requeued on
boot).

Handlers register with :func:`register_handler`. Each receives a read-only
:class:`SyncJobView` (its params + resume cursor), the shared :class:`SyncJobDeps`
(db / DuckDB storage / providers), and an ``on_progress`` callback it must call
after every chunk — that callback persists progress, pushes an SSE update, and
raises :class:`SyncJobCancelled` if the job was cancelled mid-run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from kactus_common.database.oltp.session import DatabaseSessionManager
from kactus_common.portfolio.const import AssetType
from kactus_common.sse.broker import get_sse_broker
from kactus_common.sync.const import SyncJobStatus, SyncJobType
from kactus_common.sync.model import SyncJob
from kactus_common.sync.service import SyncJobService
from kactus_data.portfolio.provider import AssetProvider
from kactus_data.storage.duckdb import DuckDBStorage
from loguru import logger

#: SSE message discriminator. Market refresh nudges carry no ``event`` key, so
#: the frontend treats ``event == "sync.progress"`` as a queue-progress update
#: and everything else as a data-refreshed nudge.
SYNC_PROGRESS_EVENT = "sync.progress"


class SyncJobCancelled(Exception):
    """Raised inside a handler's progress checkpoint when the job was cancelled."""


@dataclass(frozen=True)
class SyncJobView:
    """Immutable snapshot of a claimed job, detached from its DB session."""

    id: int
    job_type: str
    dedup_key: str
    params: dict
    cursor: str | None
    progress_done: int
    progress_total: int


@dataclass
class SyncJobDeps:
    """Everything a handler needs to do work, shared across the dispatcher."""

    db: DatabaseSessionManager
    storage: DuckDBStorage
    providers: dict[AssetType, AssetProvider]


# on_progress(done, total, cursor=None) — persists + emits SSE + may raise cancel.
ProgressFn = Callable[..., Awaitable[None]]
Handler = Callable[[SyncJobView, "SyncJobDeps", ProgressFn], Awaitable[dict]]

#: Registered job handlers, keyed by ``SyncJobType`` value.
SYNC_HANDLERS: dict[str, Handler] = {}


def register_handler(job_type: SyncJobType) -> Callable[[Handler], Handler]:
    """Decorator: bind a handler to a ``SyncJobType`` in :data:`SYNC_HANDLERS`."""

    def _decorate(fn: Handler) -> Handler:
        SYNC_HANDLERS[str(job_type)] = fn
        return fn

    return _decorate


def _view(job: SyncJob) -> SyncJobView:
    return SyncJobView(
        id=job.id,
        job_type=job.job_type,
        dedup_key=job.dedup_key,
        params=dict(job.params or {}),
        cursor=job.cursor,
        progress_done=job.progress_done,
        progress_total=job.progress_total,
    )


async def _publish(view: SyncJobView, *, status: str, done: int, total: int) -> None:
    """Push one queue-progress frame to the SSE broker (best-effort)."""
    pct = min(100, round(done * 100 / total)) if total > 0 else 0
    try:
        await get_sse_broker().publish(
            {
                "event": SYNC_PROGRESS_EVENT,
                "job_id": str(view.id),
                "job_type": view.job_type,
                "dedup_key": view.dedup_key,
                "status": status,
                "done": done,
                "total": total,
                "pct": pct,
            }
        )
    except Exception as ex:  # noqa: BLE001 — SSE is a hint; never fail a job on it
        logger.warning(f"sync.progress publish failed: {ex}")


def _make_on_progress(deps: SyncJobDeps, view: SyncJobView) -> ProgressFn:
    async def on_progress(done: int, total: int, cursor: str | None = None) -> None:
        async with deps.db.get_session() as session:
            if await SyncJobService.is_cancelled(session, view.id):
                raise SyncJobCancelled()
            job = await SyncJob.get(session, view.id)
            if job is not None:
                await SyncJobService.update_progress(
                    session, job, done=done, total=total, cursor=cursor
                )
        await _publish(view, status=str(SyncJobStatus.RUNNING), done=done, total=total)

    return on_progress


async def _finish(
    deps: SyncJobDeps,
    view: SyncJobView,
    *,
    status: SyncJobStatus,
    message: str | None = None,
    result: dict | None = None,
    done: int | None = None,
    total: int | None = None,
) -> None:
    async with deps.db.get_session() as session:
        job = await SyncJob.get(session, view.id)
        if job is not None:
            if total is not None:
                job.progress_total = total
            if done is not None:
                job.progress_done = done
            await SyncJobService.finish(
                session, job, status=status, message=message, result=result
            )


async def _run_job(deps: SyncJobDeps, view: SyncJobView) -> None:
    handler = SYNC_HANDLERS.get(view.job_type)
    if handler is None:
        logger.error(
            f"No sync handler registered for '{view.job_type}' (job {view.id})"
        )
        await _finish(
            deps,
            view,
            status=SyncJobStatus.FAILED,
            message=f"No handler for job type '{view.job_type}'",
        )
        await _publish(view, status=str(SyncJobStatus.FAILED), done=0, total=0)
        return

    on_progress = _make_on_progress(deps, view)
    try:
        result = await handler(view, deps, on_progress)
    except SyncJobCancelled:
        # The canceller already flipped status → CANCELLED; just announce it.
        logger.info(f"Sync job {view.id} ({view.job_type}) cancelled")
        await _publish(view, status=str(SyncJobStatus.CANCELLED), done=0, total=0)
        return
    except Exception as ex:  # noqa: BLE001 — one bad job must not kill the loop
        logger.exception(f"Sync job {view.id} ({view.job_type}) failed")
        await _finish(deps, view, status=SyncJobStatus.FAILED, message=str(ex))
        await _publish(view, status=str(SyncJobStatus.FAILED), done=0, total=0)
        return

    total = (
        int(result.get("total", view.progress_total)) if result else view.progress_total
    )
    await _finish(
        deps, view, status=SyncJobStatus.SUCCESS, result=result, done=total, total=total
    )
    await _publish(view, status=str(SyncJobStatus.SUCCESS), done=total, total=total)
    logger.info(f"Sync job {view.id} ({view.job_type}) done: {result}")


async def run_dispatcher(
    deps: SyncJobDeps,
    *,
    poll_interval: float = 1.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Drain the sync-job queue one job at a time until ``stop_event`` is set."""
    try:
        async with deps.db.get_session() as session:
            requeued = await SyncJobService.requeue_orphans(session)
        if requeued:
            logger.info(f"Requeued {requeued} orphaned sync job(s) on boot")
    except Exception as ex:  # noqa: BLE001 — a DB hiccup at boot must not kill us
        logger.warning(f"Orphan requeue on boot failed (will retry via loop): {ex}")

    logger.info("Sync-job dispatcher started")
    while stop_event is None or not stop_event.is_set():
        try:
            async with deps.db.get_session() as session:
                job = await SyncJobService.claim_next(session)
                view = _view(job) if job is not None else None
            if view is None:
                await asyncio.sleep(poll_interval)
                continue
            await _run_job(deps, view)
        except asyncio.CancelledError:
            raise
        except Exception as ex:  # noqa: BLE001 — keep the loop alive on any blip
            logger.exception(f"Sync dispatcher loop error: {ex}")
            await asyncio.sleep(poll_interval)
    logger.info("Sync-job dispatcher stopped")
