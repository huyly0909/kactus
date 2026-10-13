"""Lifecycle + dedup for the sync-job queue.

Used from two sides: kactus-fin enqueues PENDING jobs (inside the request's user
context, so ``created_by`` auto-populates), and the kactus-data-plane
dispatcher claims / progresses / finishes them. Both share this one service so
the FIFO + dedup rules live in a single place.
"""

from __future__ import annotations

import datetime

from kactus_common.database.oltp.models import utcnow
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .const import ACTIVE_SYNC_STATUSES, SyncJobStatus
from .model import SyncJob

#: ``status`` filter value meaning "PENDING or RUNNING" rather than one literal
#: status — the queue UI's live view, and what the active-count chip selects.
ACTIVE_STATUS_FILTER = "active"


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
    async def latest_finished_by_type(session: AsyncSession) -> list[SyncJob]:
        """The most recent *finished* job of each ``job_type`` — one row per type.

        Deliberately not derived from :meth:`list_recent`: that is a flat
        newest-first window, so a burst of one job type (a gold backfill, say)
        pushes every other type's last outcome out of it, and the caller would
        silently render "never ran" for a job that ran this morning.

        ``max(id)`` rather than a window function over ``finished_at``: ids are
        monotonic so it means the same thing, and plain GROUP BY runs
        identically on SQLite (unit tests) and Postgres.
        """
        newest = (
            select(SyncJob.job_type, func.max(SyncJob.id).label("job_id"))
            .where(SyncJob.finished_at.is_not(None))
            .group_by(SyncJob.job_type)
            .subquery()
        )
        stmt = select(SyncJob).join(newest, SyncJob.id == newest.c.job_id)
        return list((await session.scalars(stmt)).all())

    @staticmethod
    async def count_active(session: AsyncSession) -> int:
        """How many jobs are live right now, across the whole table.

        Deliberately not page- or filter-scoped: the UI's "N running" chip must
        stay truthful while the user is reading page 5 of the failed jobs.
        """
        stmt = select(func.count(SyncJob.id)).where(
            SyncJob.status.in_(list(ACTIVE_SYNC_STATUSES))
        )
        return int(await session.scalar(stmt) or 0)

    @staticmethod
    def _search_filters(
        *,
        status: str | None = None,
        job_type: str | None = None,
        job_family: str | None = None,
        source: str | None = None,
        created_from: datetime.datetime | None = None,
        created_to: datetime.datetime | None = None,
    ) -> list[ColumnElement[bool]]:
        """Build the WHERE terms shared by the page query and its COUNT."""
        terms: list[ColumnElement[bool]] = []
        if status == ACTIVE_STATUS_FILTER:
            terms.append(SyncJob.status.in_(list(ACTIVE_SYNC_STATUSES)))
        elif status:
            terms.append(SyncJob.status == status)
        if job_type:
            # Exact job — "all tasks of this scheduler job" (the jobs-pane link).
            terms.append(SyncJob.job_type == job_type)
        if job_family:
            # ``gold_backfill`` / ``gold_sync`` both belong to the "gold" family.
            # LIKE (not a JSON op) so the same SQL runs on SQLite and Postgres;
            # the underscore is escaped or "gold_" would match any 5th char.
            terms.append(SyncJob.job_type.like(f"{job_family}\\_%", escape="\\"))
        if source:
            # ``params`` is a plain JSON column: ``as_string()`` compiles to
            # json_extract on SQLite and ->> on Postgres, so this one expression
            # serves the unit tests and prod alike.
            terms.append(SyncJob.params["source"].as_string() == source)
        if created_from is not None:
            terms.append(SyncJob.create_time >= created_from)
        if created_to is not None:
            terms.append(SyncJob.create_time <= created_to)
        return terms

    @staticmethod
    async def search(
        session: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        job_type: str | None = None,
        job_family: str | None = None,
        source: str | None = None,
        created_from: datetime.datetime | None = None,
        created_to: datetime.datetime | None = None,
        order: str = "desc",
    ) -> tuple[list[SyncJob], int]:
        """One page of jobs matching the filters + the total matching count.

        Ordered on ``create_time`` (the enqueue instant), newest first by
        default. ``id`` breaks ties so a page boundary cannot drop or repeat a
        row when several jobs share a timestamp. ``created_from`` / ``created_to``
        are UTC instants — the caller resolves the user's calendar days.
        """
        terms = SyncJobService._search_filters(
            status=status,
            job_type=job_type,
            job_family=job_family,
            source=source,
            created_from=created_from,
            created_to=created_to,
        )
        total = int(
            await session.scalar(select(func.count(SyncJob.id)).where(*terms)) or 0
        )

        time_col = SyncJob.create_time
        ordering = (
            (time_col.asc(), SyncJob.id.asc())
            if order == "asc"
            else (time_col.desc(), SyncJob.id.desc())
        )
        stmt = (
            select(SyncJob)
            .where(*terms)
            .order_by(*ordering)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await session.scalars(stmt)).all()), total

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
