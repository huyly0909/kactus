"""Sync-job queue API schemas."""

from __future__ import annotations

from kactus_common.schemas import (
    AwareUTCDatetime,
    BaseSchema,
    FancyInt,
    OpaqueDict,
    Pagination,
)


class SyncJobSchema(BaseSchema):
    """One queued sync job, as surfaced to the queue UI + progress bars."""

    id: FancyInt
    job_type: str
    dedup_key: str
    params: OpaqueDict
    status: str
    progress_total: FancyInt
    progress_done: FancyInt
    progress_pct: FancyInt
    cursor: str | None = None
    message: str | None = None
    result: OpaqueDict | None = None
    created_by: FancyInt | None = None
    create_time: AwareUTCDatetime | None = None
    started_at: AwareUTCDatetime | None = None
    finished_at: AwareUTCDatetime | None = None


class EnqueueSyncJobResponse(BaseSchema):
    """Result of an enqueue: the live job + whether this call created it.

    ``created is False`` means an identical job was already PENDING/RUNNING (the
    dedup collapsed the click), so the UI toasts "already queued" rather than
    "queued" — either way ``job`` is the row now holding that slot.
    """

    job: SyncJobSchema
    created: bool


class SyncJobListSchema(BaseSchema):
    """The queue as the UI reads it: the live FIFO run + recent history.

    ``active`` is oldest-first (queue order, what runs next); ``recent`` is
    newest-first regardless of status (the history table). ``recent`` may repeat
    an ``active`` row — the UI keys by ``id`` and renders each once.
    """

    active: list[SyncJobSchema] = []
    recent: list[SyncJobSchema] = []


class SyncJobPageSchema(Pagination[SyncJobSchema]):
    """One filtered, ordered page of the queue + the global live count.

    ``active_count`` is intentionally *not* page- or filter-scoped: it counts
    every PENDING/RUNNING job, so the UI's "N running" chip stays truthful while
    the user is paging through finished history.
    """

    # Plain ``int``, not ``FancyInt``: this is a small count sitting beside the
    # envelope's own ``total`` / ``page`` / ``page_size``, and FancyInt exists to
    # protect 64-bit *ids* from JS precision loss. Serializing it as a string
    # while its neighbours stay numbers would just make the client cast it back.
    active_count: int = 0
