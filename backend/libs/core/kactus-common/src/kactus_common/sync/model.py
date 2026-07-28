"""Sync-job queue ORM model — a durable FIFO queue for DuckDB writes.

One row per queued sync (gold backfill / sync-now; stock later). The data plane
runs a single dispatcher that claims the oldest PENDING row, executes it, and
persists progress after each chunk so a restart resumes from the saved
``cursor``. Postgres, not Redis: the queue must survive a data-plane restart
and carry per-job audit (who enqueued it, what it produced).
"""

from __future__ import annotations

import datetime

from kactus_common.database.oltp.models import AuditMixin, Base, ModelMixin
from sqlalchemy import JSON, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .const import SyncJobStatus


class SyncJob(Base, ModelMixin, AuditMixin):
    """One queued data-sync unit of work with progress + resume state.

    ``create_time`` is the enqueue instant (FIFO ordering key); ``started_at``
    is when the dispatcher first moved it to RUNNING. ``cursor`` is the
    handler-defined resume point (e.g. the last completed window's end date).
    """

    __tablename__ = "sync_jobs"

    job_type: Mapped[str] = mapped_column(String(32), index=True)
    # Collapses duplicate enqueues: one live job per key (see the partial index
    # below). e.g. "gold_backfill:sjc", "gold_sync:all".
    dedup_key: Mapped[str] = mapped_column(String(128), index=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(16), default=SyncJobStatus.PENDING, index=True
    )
    progress_total: Mapped[int] = mapped_column(Integer, default=0)
    progress_done: Mapped[int] = mapped_column(Integer, default=0)
    cursor: Mapped[str | None] = mapped_column(String(64), default=None)
    message: Mapped[str | None] = mapped_column(Text, default=None)
    result: Mapped[dict | None] = mapped_column(JSON, default=None)
    started_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime.datetime | None] = mapped_column(default=None)

    __table_args__ = (
        # At most one live (pending/running) job per dedup_key — the DB backstop
        # behind the app-level enqueue check and the "disable if queued" UI.
        # Declared for both dialects: Postgres in prod, SQLite in unit tests.
        Index(
            "uq_sync_job_active_dedup",
            "dedup_key",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
            sqlite_where=text("status IN ('pending', 'running')"),
        ),
        # The queue UI orders and pages on ``create_time`` (newest first) over a
        # table that only grows — without this every page is a full sort.
        Index("ix_sync_jobs_create_time", "create_time"),
    )

    @property
    def progress_pct(self) -> int:
        """Whole-percent progress (0–100); 0 while total is unknown."""
        if self.progress_total <= 0:
            return 0
        return min(100, round(self.progress_done * 100 / self.progress_total))
