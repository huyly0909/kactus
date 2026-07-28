"""Market admin API — superuser-only gold history import + sync-job queue.

Two responsibilities, both superuser:

- **Gold CSV import** — takes the browser's multipart upload, applies a size
  guard, and forwards each file's raw bytes to the data plane (the only process
  that may write DuckDB). Parsing lives there, beside the table definition.
- **Sync-job queue** — enqueues gold backfill / sync-now jobs and lists/cancels
  the shared FIFO queue. Enqueue is just a Postgres insert (``created_by`` auto
  from the request user), so it happens here rather than over HTTP to the data
  plane; the single data-plane dispatcher then claims and runs the row.
"""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import File, Query, Request, UploadFile
from kactus_common.exceptions import NotFoundError, ValidationError
from kactus_common.router import KactusAPIRouter, multipart_upload_openapi
from kactus_common.sync.schema import (
    EnqueueSyncJobResponse,
    SyncJobListSchema,
    SyncJobPageSchema,
    SyncJobSchema,
)
from kactus_common.sync.service import SyncJobService
from kactus_fin import data_client
from kactus_fin.dependencies import provide_session
from kactus_gold.const import GoldJobType
from kactus_gold.schema import GoldImportResultSchema
from kactus_gold.sync import (
    GoldBackfillRequest,
    GoldSyncRequest,
    gold_backfill_dedup_key,
    gold_backfill_min,
    gold_sync_dedup_key,
)
from sqlalchemy.ext.asyncio import AsyncSession

#: Largest known backfill file is ~7.4 MB (PNJ, 92k rows); 25 MB leaves room
#: for growth while still bounding what gets buffered in memory per file.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

#: Queue page size — the default fits a screen without scrolling; the cap keeps
#: one request from asking for the whole (only-ever-growing) table.
DEFAULT_QUEUE_PAGE_SIZE = 20
MAX_QUEUE_PAGE_SIZE = 200

#: Timezone a user's calendar-day filter is read in when they have none saved.
DEFAULT_USER_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

router = KactusAPIRouter(prefix="/api/market", tags=["market-admin"])


def _user_tz(request: Request) -> ZoneInfo:
    """The requesting user's timezone — the zone their date filters mean.

    Falls back to VN rather than UTC: a stale or unparseable value must not
    silently shift the day boundary a filtered page is cut on.
    """
    name = getattr(request.state.user, "timezone", None)
    if not name:
        return DEFAULT_USER_TZ
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return DEFAULT_USER_TZ


@router.post("/gold/import", **multipart_upload_openapi("files"))
async def import_gold_history(
    files: list[UploadFile] = File(...),
) -> list[GoldImportResultSchema]:
    """Import gold-history CSVs, one result per file (order preserved)."""
    results: list[GoldImportResultSchema] = []
    for upload in files:
        content = await upload.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValidationError(
                f"File '{upload.filename}' exceeds the "
                f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit"
            )
        results.append(
            await data_client.import_gold_history(
                upload.filename or "upload.csv", content
            )
        )
    return results


@router.post("/gold/backfill")
@provide_session
async def enqueue_gold_backfill(
    request: Request, session: AsyncSession, body: GoldBackfillRequest
) -> EnqueueSyncJobResponse:
    """Queue a gold-history backfill for one ``(source[, code])`` series.

    ``date_from`` is clamped up to the source's earliest available date so an
    over-wide "all" request never fetches windows that can only come back empty.
    """
    source = str(body.source)
    floor = gold_backfill_min(source)
    date_from = max(body.date_from, floor)
    if date_from > body.date_to:
        raise ValidationError(
            f"Requested range ends before {source}'s earliest data",
            tip=f"{source} history starts {floor.isoformat()}",
            data={"source": source, "min": floor.isoformat()},
        )
    code = body.code or None
    params = {
        "source": source,
        "date_from": date_from.isoformat(),
        "date_to": body.date_to.isoformat(),
    }
    if code:
        params["code"] = code
    job, created = await SyncJobService.enqueue(
        session,
        job_type=GoldJobType.GOLD_BACKFILL,
        params=params,
        dedup_key=gold_backfill_dedup_key(source, code),
    )
    return EnqueueSyncJobResponse(
        job=SyncJobSchema.model_validate(job), created=created
    )


@router.post("/gold/sync")
@provide_session
async def enqueue_gold_sync(
    request: Request, session: AsyncSession, body: GoldSyncRequest
) -> EnqueueSyncJobResponse:
    """Queue a gold sync-now (board refresh + intraday tick) for a source or all."""
    source = (body.source or "all").lower()
    job, created = await SyncJobService.enqueue(
        session,
        job_type=GoldJobType.GOLD_SYNC,
        params={"source": source},
        dedup_key=gold_sync_dedup_key(source),
    )
    return EnqueueSyncJobResponse(
        job=SyncJobSchema.model_validate(job), created=created
    )


@router.get("/sync/jobs")
@provide_session
async def list_sync_jobs(
    request: Request, session: AsyncSession, limit: int = 50
) -> SyncJobListSchema:
    """The queue: live jobs (FIFO order) + recent history (newest first)."""
    active = await SyncJobService.list_active(session)
    recent = await SyncJobService.list_recent(session, limit=limit)
    return SyncJobListSchema(
        active=[SyncJobSchema.model_validate(j) for j in active],
        recent=[SyncJobSchema.model_validate(j) for j in recent],
    )


@router.get("/sync/jobs/search")
@provide_session
async def search_sync_jobs(
    request: Request,
    session: AsyncSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_QUEUE_PAGE_SIZE, ge=1, le=MAX_QUEUE_PAGE_SIZE),
    status: str | None = None,
    type: str | None = None,
    source: str | None = None,
    created_from: datetime.date | None = None,
    created_to: datetime.date | None = None,
    order: str = "desc",
) -> SyncJobPageSchema:
    """One filtered page of the queue, newest first, + the global live count.

    ``status`` takes a literal ``SyncJobStatus`` or ``"active"`` (pending OR
    running); ``type`` is the job family (``gold``), ``source`` matches
    ``params.source``. ``created_from`` / ``created_to`` are the *user's*
    calendar days — resolved to UTC instants here, so picking "today" means
    their today, not UTC's.
    """
    tz = _user_tz(request)
    created_from_dt = (
        datetime.datetime.combine(created_from, datetime.time.min, tzinfo=tz)
        if created_from
        else None
    )
    created_to_dt = (
        datetime.datetime.combine(created_to, datetime.time.max, tzinfo=tz)
        if created_to
        else None
    )

    jobs, total = await SyncJobService.search(
        session,
        page=page,
        page_size=page_size,
        status=status,
        job_family=type,
        source=source,
        created_from=created_from_dt,
        created_to=created_to_dt,
        order="asc" if order == "asc" else "desc",
    )
    return SyncJobPageSchema(
        total=total,
        page=page,
        page_size=page_size,
        items=[SyncJobSchema.model_validate(j) for j in jobs],
        active_count=await SyncJobService.count_active(session),
    )


@router.post("/sync/jobs/{job_id}/cancel")
@provide_session
async def cancel_sync_job(
    request: Request, session: AsyncSession, job_id: int
) -> SyncJobSchema:
    """Cancel a live job. A RUNNING one stops at its next progress checkpoint."""
    job = await SyncJobService.cancel(session, job_id)
    if job is None:
        raise NotFoundError("No such sync job", data={"job_id": job_id})
    return SyncJobSchema.model_validate(job)
