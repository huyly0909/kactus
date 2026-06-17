---
description: FastAPI endpoint conventions for Usonia
paths:
  - "**/api.py"
  - "**/api/**"
---

# API Conventions

Every simulator's task + file endpoints follow the **unified envelope shape**
introduced in the 2026-05 standardisation. AI agents consume this OpenAPI
spec directly, so consistency matters more than local convenience.

## Router

Always use `UsoniaAPIRouter`, never `fastapi.APIRouter`:

```python
from usonia_common.router import UsoniaAPIRouter
router = UsoniaAPIRouter(prefix="/api/projects", tags=["projects"])
```

## Response Pattern

Return plain data objects. `UsoniaAPIRouter` auto-wraps in `ResponseModel(data=...)`:

```python
@router.get("")
async def list_projects() -> Pagination[ProjectSchema]:
    return Pagination(total=len(items), page=1, page_size=20, items=items)
```

Never manually wrap in `ResponseModel`.

## OpenAPI metadata — required on every public route

Every endpoint must declare `summary`, `description`, `operation_id`, and the
shared `responses` map so AI agents see the error envelope shape:

```python
from usonia_common.exceptions import ErrorResponse

ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Bad request."},
    404: {"model": ErrorResponse, "description": "Resource not found."},
    422: {"model": ErrorResponse, "description": "Validation error."},
}

@router.get(
    "/{task_id}",
    summary="Get task by id",
    description="Returns the unified TaskEnvelope.",
    operation_id="sap10_get_task",
    responses=ERROR_RESPONSES,
)
async def get_task(task_id: int, ...) -> Sap10TaskEnvelope:
    ...
```

`operation_id` is stable snake_case (`<simulator>_<action>`).

## Pagination

Use `PageParams` (`Depends`) + the `paginate()` helper:

```python
from usonia_common.pagination import PageParams, paginate

@router.get("", operation_id="sap10_list_files", responses=ERROR_RESPONSES)
@provide_session
async def list_files(
    pagination: PageParams = Depends(),
    file_kind: Sap10FileKind | None = None,
    user_id: str = Depends(require_user_id),
    session: AsyncSession = None,
) -> Pagination[Sap10FileEnvelope]:
    query = select(Sap10File).where(Sap10File.user_id == user_id)
    if file_kind is not None:
        query = query.where(Sap10File.file_kind == file_kind)
    return await paginate(session, query, pagination, schema=Sap10FileEnvelope)
```

`PageParams` enforces `page ≥ 1` and `1 ≤ page_size ≤ 100`. The returned
`Pagination[T]` carries `total`, `page`, `page_size`, `items`.

For task lists that compose envelopes manually (because of eager loading or
status mapping), call `paginator()` directly and build the `Pagination[T]`
yourself:

```python
items, total = await paginator(session, query, page=pagination.page, page_size=pagination.page_size)
return Pagination[Sap10TaskEnvelope](
    total=total,
    page=pagination.page,
    page_size=pagination.page_size,
    items=[sap10_task_to_envelope(t) for t in items],
)
```

## Task Envelope

Every simulator's `POST /tasks`, `GET /tasks`, and `GET /tasks/{task_id}`
returns `TaskEnvelope[<Sim>Result]`. Only the inner `result` differs.

```python
# packages/usonia-common/src/usonia_common/task/envelope.py
class TaskEnvelope(BaseSchema, Generic[TResult]):
    task_id: FancyInt
    simulator: TaskType
    run_type: TaskRunType
    status: JobStatus
    version: int
    created_at: datetime | None
    updated_at: datetime | None
    result: TResult | None   # populated on SUCCESS
    error: str | None         # populated on FAILED
```

Pattern per simulator:

```python
# <sim>/task/schema.py
class Sap10Result(BaseSchema):
    sap: FancyFloat | None = None
    ei: FancyFloat | None = None

Sap10TaskEnvelope = TaskEnvelope[Sap10Result]

def sap10_task_to_envelope(task: Sap10Task) -> Sap10TaskEnvelope:
    return Sap10TaskEnvelope(
        task_id=task.id,
        simulator=TaskType.SAP10,
        run_type=TaskRunType.SYNC,
        status=...,  # map TaskStatus → JobStatus
        version=task.version,
        created_at=task.created_at,
        updated_at=task.updated_at,
        result=Sap10Result(...) if task.output else None,
        error=task.error_message,
    )
```

Submit endpoints return the envelope; override `run_type` so the response
echoes what the caller submitted:

```python
envelope = sap10_task_to_envelope(task)
return envelope.model_copy(update={"run_type": body.run_type})
```

Task body schemas (`<Sim>SubmitTaskBody`) carry `version` + `run_type` —
**never** as URL path segments or query params.

## File Envelope + explicit `file_kind`

Every file endpoint returns a `FileEnvelope`-shaped schema:
`id, file_name, file_kind, version, size, user_id, created_at, updated_at`.

The **`file_kind` is always explicit** — never inferred from the filename.
Two patterns depending on how many kinds a simulator has:

### Single-kind (SAP10, SBEM, PHPP)

Add an explicit `file_kind: <Sim>FileKind = Form(<Default>)` form field. The
default exists because there's only one valid kind today, but the field is
documented so AI agents see the available values:

```python
from fastapi import Form

@router.post(
    "",
    summary="Upload SAP10 file",
    operation_id="sap10_upload_file",
    responses=ERROR_RESPONSES,
)
async def upload_file(
    file: UploadFile,
    file_kind: Sap10FileKind = Form(Sap10FileKind.SAP10_XML),
    user_id: str = Depends(require_user_id),
    version: int = DEFAULT_VERSION,
    session: AsyncSession = None,
) -> Sap10FileEnvelope:
    ...
```

### Multi-kind (EnergyPlus, Radiance, HEM)

Use `multipart_upload_openapi_multi({...})` — the **field name is the file
kind**:

```python
from usonia_common.router import multipart_upload_openapi_multi

@router.post(
    "",
    summary="Upload EnergyPlus inputs",
    operation_id="eplus_upload_files",
    responses=ERROR_RESPONSES,
    **multipart_upload_openapi_multi({
        "weather": "Weather File (.epw)",
        "idf": "IDF File (.idf)",
    }),
)
async def upload_files(
    weather: UploadFile = File(None),
    idf: UploadFile = File(None),
    ...
) -> list[EplusFileEnvelope]:
    ...
```

The single-field helper `multipart_upload_openapi("files")` is still
available for the rare endpoint with a single typed-list field.

## Model conventions for envelopes

The simulator-base `BaseModel` and `FileBase` expose `created_at` /
`updated_at` `@property`s (aliasing `ModelMixin.create_time` / `update_time`)
plus `size` (from `len(file)`) so envelope schemas with `from_attributes=True`
map cleanly without per-schema aliases. When adding a new file model, add a
`file_kind` column **or** `@property` so the envelope can read it.

## Database Access

```python
from usonia_common.database.oltp.session import provide_session

@router.get("/{id}")
@provide_session
async def get_project(id: int, session: AsyncSession) -> ProjectSchema:
    project = await Project.get_or_404(session, id)
    return ProjectSchema.model_validate(project)
```

## Errors

Raise `BaseError` subclasses (`NotFoundException`, `BadRequest`, etc.) — the
global handler emits the unified envelope:

```json
{
  "code": "NOT_FOUND",
  "msg": "Sap10 task id=42 not found",
  "data": null,
  "error": { "type": "NotFoundException", "detail": "..." }
}
```

Every `BaseError` subclass has a `error_code: ClassVar[str]` (`NOT_FOUND`,
`VALIDATION_ERROR`, `INVALID_FILE`, etc.) used by clients for branching.
Declare the envelope shape on every operation via the shared
`ERROR_RESPONSES` map (see "OpenAPI metadata" above) so the OpenAPI spec
documents it.

## File Download

```python
from usonia_common.responses import FileDownloadResponse

@router.get("/download", response_model=None)
async def download_file(...):
    return FileDownloadResponse(content=item.file, filename=item.file_name)
```

Set `response_model=None` on download endpoints.

## Checklist

- Uses `UsoniaAPIRouter`
- Every public route has `summary`, `description`, `operation_id`, `responses=ERROR_RESPONSES`
- List endpoints take `PageParams` via `Depends(...)` and return `Pagination[T]`
- Task endpoints return `TaskEnvelope[<Sim>Result]` (`/tasks`, `/tasks/{task_id}`, `POST /tasks`)
- File endpoints return `<Sim>FileEnvelope` with explicit `file_kind` (`Form(...)` or multipart field name)
- Schema inherits from `BaseSchema`
- Numeric fields use `FancyInt` / `FancyFloat`
- Tests written for all endpoints (clone the SAP10 pattern at `packages/usonia-simulators/tests/sap10/`)
