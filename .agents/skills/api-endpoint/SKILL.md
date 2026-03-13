---
name: api-endpoint
description: Use when creating or modifying FastAPI API endpoints. Covers KactusAPIRouter usage, permission patterns, response schemas, and database access in endpoints.
---

# API Endpoint Skill

## Router Setup

Always use `KactusAPIRouter`, never `fastapi.APIRouter`:

```python
from kactus_common.router import KactusAPIRouter

router = KactusAPIRouter(prefix="/api/projects", tags=["projects"])
```

## Response Pattern

Endpoints return **plain data objects** — `KactusAPIRouter` auto-wraps them in `ResponseModel(data=...)`.

```python
from kactus_common.schemas import Pagination

# ✅ Correct — return plain data
@router.get("")
async def list_projects(request: Request) -> Pagination[ProjectSchema]:
    return Pagination(total=len(items), items=items)

@router.get("/{id}")
async def get_project(id: int) -> ProjectSchema:
    return ProjectSchema.model_validate(project)

# ❌ Wrong — do NOT manually wrap in ResponseModel
@router.get("", response_model=ResponseModel[Pagination[ProjectSchema]])
async def list_projects(...) -> ResponseModel[...]:
    return ResponseModel(data=Pagination(...))
```

## Database Access in Endpoints

Use the `provide_session` decorator or `get_db()` directly:

```python
from kactus_common.database.oltp.session import get_db, provide_session
from sqlalchemy.ext.asyncio import AsyncSession

# Pattern 1: provide_session decorator
@router.get("/{id}")
@provide_session
async def get_project(id: int, session: AsyncSession) -> ProjectSchema:
    project = await Project.get_or_404(session, id)
    return ProjectSchema.model_validate(project)

# Pattern 2: get_db() context manager
@router.post("")
async def create_project(body: CreateProjectRequest) -> ProjectSchema:
    async with get_db().get_session() as session:
        project = await ProjectService.create(session, body)
    return ProjectSchema.model_validate(project)
```

## User Access — `request.state.user`

In session routes, the user is set automatically by AppManager's auth dependency. Access via `request.state.user`:

```python
@router.get("/me/projects")
async def my_projects(request: Request) -> list[ProjectSchema]:
    user = request.state.user          # ✅ correct
    # user = Depends(get_current_user)  # ❌ wrong
    ...
```

## Permission Decorator

```python
from kactus_common.authorization.decorators import permission
from kactus_common.authorization.const import PermissionAct
from .const import ProjectPermission

@router.put("/{id}")
@permission(ProjectPermission.project, PermissionAct.write)
async def update_project(request: Request, id: int, body: UpdateRequest) -> ProjectSchema:
    user = request.state.user
    ...
```

## Schema Rules

- All schemas inherit from `BaseSchema` (never `BaseModel` directly)
- Use `FancyInt` / `FancyFloat` for numeric fields in API responses
- Always return Pydantic schemas from endpoints — never raw dicts
- Set `response_model` explicitly only for non-standard responses (FileResponse, StreamingResponse)

## Checklist

1. [ ] Uses `KactusAPIRouter`, not `fastapi.APIRouter`
2. [ ] Returns plain data objects (no manual `ResponseModel` wrapping)
3. [ ] Schema inherits from `BaseSchema`
4. [ ] Numeric fields use `FancyInt` / `FancyFloat`
5. [ ] Uses `request.state.user` for user access (not `Depends`)
6. [ ] Has `@permission` decorator for protected endpoints
7. [ ] Tests written for all new endpoints
