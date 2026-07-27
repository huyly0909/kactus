"""Lifecycle + dedup for the sync-job queue.

Used from two sides: kactus-fin enqueues PENDING jobs (inside the request's user
context, so ``created_by`` auto-populates), and the kactus-data-plane
dispatcher claims / progresses / finishes them. Both share this one service so
the FIFO + dedup rules live in a single place.
"""

from __future__ import annotations

from kactus_common.database.oltp.models import utcnow
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .const import ACTIVE_SYNC_STATUSES, SyncJobStatus
from .model import SyncJob


class SyncJobService:
    """Enqueue, claim (FIFO), progress, and finish queued sync jobs."""

    @staticmethod
    async def enqueue(
        session: AsyncSession,
        *,
        job_type: str,
        params: dict,
        dedup_key: str,
    ) -> tuple[SyncJob, bool]:
        """Insert a PENDING job, or return the live one already queued.

        Returns ``(job, created)``; ``created is False`` means an identical job
        (same ``dedup_key``) is already PENDING/RUNNING — the caller surfaces
        "already queued" and does not stack a duplicate.
        """
        existing = await SyncJobService._active_by_key(session, dedup_key)
        if existing is not None:
            return existing, False

        job = SyncJob.init(
            job_type=str(job_type),
            dedup_key=dedup_key,
            params=params,
            status=str(SyncJobStatus.PENDING),
        )
        session.add(job)
        try:
            await session.commit()
        except IntegrityError:
            # Lost the race against the partial unique index — return the winner.
            await session.rollback()
            existing = await SyncJobService._active_by_key(session, dedup_key)
            if existing is not None:
                return existing, False
            raise
        await session.refresh(job)
        return job, True

    @staticmethod
    async def claim_next(session: AsyncSession) -> SyncJob | None:
        """Move the oldest PENDING job to RUNNING and return it (FIFO).

        A single dispatcher runs this, so no row lock is needed; enqueues happen
        elsewhere and only ever add PENDING rows.
        """
        stmt = (
            select(SyncJob)
            .where(SyncJob.status == str(SyncJobStatus.PENDING))
            .order_by(SyncJob.create_time.asc())
            .limit(1)
        )
        job = (await session.scalars(stmt)).first()
        if job is None:
            return None
        job.status = str(SyncJobStatus.RUNNING)
        if job.started_at is None:
            job.started_at = utcnow()
        await job.save(session)
        return job

    @staticmethod
    async def update_progress(
        session: AsyncSession,
        job: SyncJob,
        *,
        done: int,
        total: int | None = None,
        cursor: str | None = None,
    ) -> SyncJob:
        """Persist chunk progress so a restart resumes from ``cursor``."""
        job.progress_done = done
        if total is not None:
            job.progress_total = total
        if cursor is not None:
            job.cursor = cursor
        await job.save(session)
        return job

    @staticmethod
    async def finish(
        session: AsyncSession,
        job: SyncJob,
        *,
        status: SyncJobStatus,
        message: str | None = None,
        result: dict | None = None,
    ) -> SyncJob:
        """Mark the job terminal (SUCCESS / FAILED / CANCELLED)."""
        job.status = str(status)
        job.message = message
        if result is not None:
            job.result = result
        job.finished_at = utcnow()
        await job.save(session)
        return job

    @staticmethod
    async def requeue_orphans(session: AsyncSession) -> int:
        """Return crashed RUNNING jobs to PENDING on dispatcher boot.

        Progress + cursor are preserved, so the handler resumes rather than
        restarts. Returns how many were requeued.
        """
        stmt = select(SyncJob).where(SyncJob.status == str(SyncJobStatus.RUNNING))
        orphans = list((await session.scalars(stmt)).all())
        for job in orphans:
            job.status = str(SyncJobStatus.PENDING)
        if orphans:
            await session.commit()
        return len(orphans)

    @staticmethod
    async def cancel(session: AsyncSession, job_id: int) -> SyncJob | None:
        """Cancel a live job (PENDING/RUNNING). No-op on a finished one.

        A RUNNING job stops at its next ``on_progress`` checkpoint; a PENDING
        one is simply never claimed.
        """
        job = await SyncJob.get(session, job_id)
        if job is None or job.status not in ACTIVE_SYNC_STATUSES:
            return job
        job.status = str(SyncJobStatus.CANCELLED)
        job.finished_at = utcnow()
        await job.save(session)
        return job

    @staticmethod
    async def is_cancelled(session: AsyncSession, job_id: int) -> bool:
        """Fresh read of whether a job has been cancelled (mid-run checkpoint)."""
        status = await session.scalar(
            select(SyncJob.status).where(SyncJob.id == job_id)
        )
        return status == str(SyncJobStatus.CANCELLED)

    @staticmethod
    async def list_active(session: AsyncSession) -> list[SyncJob]:
        """Live jobs (PENDING/RUNNING), oldest first (queue order)."""
        stmt = (
            select(SyncJob)
            .where(SyncJob.status.in_(list(ACTIVE_SYNC_STATUSES)))
            .order_by(SyncJob.create_time.asc())
        )
        return list((await session.scalars(stmt)).all())

    @staticmethod
    async def list_recent(session: AsyncSession, *, limit: int = 50) -> list[SyncJob]:
        """Most-recent jobs, newest first (queue history)."""
        stmt = select(SyncJob).order_by(SyncJob.create_time.desc()).limit(limit)
        return list((await session.scalars(stmt)).all())

    @staticmethod
    async def active_keys(session: AsyncSession) -> set[str]:
        """The ``dedup_key``s that are live now — powers "disable if queued"."""
        stmt = select(SyncJob.dedup_key).where(
            SyncJob.status.in_(list(ACTIVE_SYNC_STATUSES))
        )
        return set((await session.scalars(stmt)).all())

    @staticmethod
    async def _active_by_key(session: AsyncSession, dedup_key: str) -> SyncJob | None:
        stmt = (
            select(SyncJob)
            .where(
                SyncJob.dedup_key == dedup_key,
                SyncJob.status.in_(list(ACTIVE_SYNC_STATUSES)),
            )
            .order_by(SyncJob.create_time.desc())
            .limit(1)
        )
        return (await session.scalars(stmt)).first()
