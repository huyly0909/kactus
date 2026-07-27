"""Sync-job queue constants and enums."""

from __future__ import annotations

from enum import StrEnum


class SyncJobType(StrEnum):
    """The kind of work a queued sync job performs.

    Gold is the first consumer; stock crawls migrate onto the queue later, so a
    new member lands here without a schema change.
    """

    GOLD_BACKFILL = "gold_backfill"
    GOLD_SYNC = "gold_sync"


class SyncJobStatus(StrEnum):
    """Lifecycle of a queued sync job."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: Statuses that count as "live": a job in one of these blocks a duplicate
#: enqueue (the partial unique index + the app-level check) and disables its
#: trigger button on the UI.
ACTIVE_SYNC_STATUSES: frozenset[str] = frozenset(
    {SyncJobStatus.PENDING, SyncJobStatus.RUNNING}
)
