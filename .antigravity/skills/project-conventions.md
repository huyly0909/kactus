---
name: project-conventions
description: Core architecture, coding conventions, and guardrails for the kactus monorepo. Use on every task involving code changes in the kactus project.
---

# Kactus Monorepo — Project Conventions

> **Other skills**: See `testing.md`, `feature-scaffold.md`, `api-endpoint.md`, `database-migration.md`, `cli-command.md` for detailed workflows.

## Architecture

Kactus is a **uv workspaces** monorepo with 5 packages:

| Package | Import As | Purpose | Port |
|---------|-----------|---------|------|
| `kactus-common` | `kactus_common` | Shared infrastructure — database clients, schemas, events, logging, exceptions | — |
| `kactus-data` | `kactus_data` | Data processing, scraping, ETL pipelines | — |
| `kactus-fin` | `kactus_fin` | FastAPI backend server (main API) | 17600 |
| `kactus-fin-gateway` | `kactus_fin_gateway` | FastAPI gateway server (public APIs) | 17601 |
| `docker-hub` | — | Docker Compose configs for dev/stag/prod deployment | — |

### Dependency Flow (One-Way)

```
kactus-fin  ──────┐
kactus-fin-gateway ──┤──▶ kactus-common
kactus-data  ─────┘
```

**Never import from kactus-fin, kactus-fin-gateway, or kactus-data into kactus-common.**

## Directory Structure

```
kactus/
├── packages/
│   ├── kactus-common/src/kactus_common/
│   │   ├── database/{duckdb/, oltp/}   # DuckDB (OLAP), SQLAlchemy async (OLTP)
│   │   ├── events/                     # Event dispatch (blinker, fastapi-events)
│   │   ├── user/                       # Shared user feature (model, schema, service, auth)
│   │   ├── cli.py, exceptions.py, schemas.py, logging.py, config.py, router.py
│   │   └── tests/
│   ├── kactus-data/src/kactus_data/
│   │   ├── sources/{gold/, stock/, company/, finance/, coin/}
│   │   ├── storage/, cli/, pipeline.py
│   │   └── tests/
│   ├── kactus-fin/src/kactus_fin/
│   │   ├── api/, cli/, auth/
│   │   ├── app.py, config.py, dependencies.py
│   │   └── tests/
│   ├── kactus-fin-gateway/src/kactus_fin_gateway/
│   │   ├── api/, cli/, app.py, config.py
│   │   └── tests/
│   └── docker-hub/{Dockerfile.*, dev/, stag/, prod/}
├── manage.py                           # Centralized CLI entry point
├── pyproject.toml                      # Workspace root
└── pytest.ini                          # Test configuration
```

## Tech Stack

- **Python 3.12+**, managed by **uv** workspaces
- **FastAPI** + **SQLAlchemy 2.0 (async)** + **Pydantic v2** / **pydantic-settings**
- **DuckDB** — OLAP, **Alembic** — migrations, **loguru** — logging
- **Typer** (`AsyncTyper`), **Docker Compose**, **pre-commit** (isort, autoflake, black, flake8)
- **pytest + pytest-asyncio** — testing (in-memory SQLite via aiosqlite)

## Where to Put Code

| You need to... | Put it in... |
|----------------|-------------|
| Add a shared feature (user, auth) | `kactus-common/<feature>/` |
| Add an app-specific feature | `<app-package>/<feature>/` (e.g. `kactus-fin/billing/`) |
| Add shared infra (DB, events, logging) | `kactus-common/` (top-level modules) |
| Add a new exception type | `kactus_common/exceptions.py` (subclass `KactusException`) |
| Add a new data source / scraper | `kactus-data/sources/<domain>/` |
| Add a new ETL job | `kactus-data/jobs/` |
| Add a new API endpoint (main) | `kactus-fin/api/` or `kactus-fin/<feature>/api.py` |
| Add a new API endpoint (gateway) | `kactus-fin-gateway/api/` |
| Add shared Pydantic models | `kactus-common/<feature>/schema.py` or `kactus-common/schemas.py` |

## Coding Conventions

### Typing — Modern Python 3.12+ Syntax

```python
# ✅ Correct
def process(items: list[str], config: dict[str, int] | None = None) -> str | None: ...

# ❌ Wrong — don't use typing.Dict, typing.List, typing.Union, typing.Optional
```

### Imports — Full Package Paths

```python
# ✅ Correct
from kactus_common.database.duckdb.client import DatabaseClient
from kactus_common.database.oltp.session import get_db
from kactus_common.exceptions import NotFoundError
from kactus_common.schemas import BaseSchema

# ❌ Wrong — never use relative imports across packages
from ..kactus_common import DatabaseClient
```

### Schemas (Pydantic)

All Pydantic schemas **must** inherit from `BaseSchema`:

```python
from kactus_common.schemas import BaseSchema, FancyInt, FancyFloat

class UserSchema(BaseSchema):
    id: FancyInt                    # serialises int → str in JSON
    name: str
    balance: FancyFloat             # serialises float → str in JSON
    email: str | None = None
```

`BaseSchema` provides: whitespace stripping, empty-string-to-None conversion, `from_attributes=True` for ORM loading.

**API responses** must always use Pydantic schemas — never return raw dicts. Use `FancyInt` / `FancyFloat` for numeric fields to avoid JavaScript precision loss.

### OLTP Models (SQLAlchemy)

```python
from kactus_common.database.oltp.models import Base, ModelMixin, AuditMixin, LogicalDeleteMixin

class User(Base, ModelMixin, AuditMixin, LogicalDeleteMixin):
    __tablename__ = "users"
    name: Mapped[str] = mapped_column()
    email: Mapped[str | None] = mapped_column(default=None)
```

- `ModelMixin` → snowflake `id`, `create_time`, `update_time`
- `AuditMixin` → `created_by`, `updated_by` (auto-populated from ContextVar, do NOT set manually)
- `AuditCreatorMixin` → `created_by` only
- `LogicalDeleteMixin` → soft-delete via `deleted_timestamp`

> Custom column types (`PasswordHash`, `DateTimeTzAware`, etc.) — see `database-migration.md`

### Database Access — `get_db()` Singleton

```python
from kactus_common.database.oltp.session import get_db

async with get_db().get_session() as session:
    user = await User.get_or_404(session, user_id)
```

> Endpoint DB patterns (`provide_session`, etc.) — see `api-endpoint.md`

### Settings Pattern

Settings follow an inheritance chain. **kactus-common does NOT load `.env` files** — only entry-point packages do:

```
BaseKactusSettings → CommonSettings → DataSettings → Settings (loads .env)
```

- Access settings via the registry proxy: `from kactus_common.config import settings`
- Each entry-point package registers its settings at startup via `register_settings()`
- Use `@lru_cache` on the package's `get_settings()` function

### Exception Pattern

```python
from kactus_common.exceptions import NotFoundError, DatabaseError

raise NotFoundError("User not found", tip="Check the user ID", data={"user_id": user_id})
```

For **package-specific** exceptions, subclass `KactusException` — caught by the FastAPI handler automatically.

### Background Tasks & Events

```python
from kactus_common.events import register_handler, BaseEventName, BaseEventPayload

class MyEvents(BaseEventName):
    USER_CREATED = "user_created"

class UserCreatedPayload(BaseEventPayload):
    __event_name__ = MyEvents.USER_CREATED
    user_id: int

@register_handler(MyEvents.USER_CREATED)
async def on_user_created(*, event_name, payload: UserCreatedPayload): ...

# Dispatch
await UserCreatedPayload(user_id=123).dispatch(background=True)
```

### Logging

Use **loguru** exclusively:
```python
from loguru import logger

logger.info("Processing user {user_id}", user_id=42)
```

❌ Never use `import logging` / `logging.getLogger(__name__)`.

## Quick Commands

```bash
# Servers
python manage.py fin dev                # dev with hot-reload (port 17600)
python manage.py fin-gw dev             # gateway dev (port 17601)

# Dependencies
cd packages/kactus-common && uv add <package>
uv sync --package kactus-fin

# Pre-commit
pre-commit install && pre-commit run --all-files
```

> DB migrations — see `database-migration.md` | Testing — see `testing.md` | CLI — see `cli-command.md`

## Don't Do This

- ❌ Use `Union[A, B]`, `Optional[X]`, `Dict`, `List` — use `A | B`, `X | None`, `dict`, `list`
- ❌ Return raw dicts from API endpoints — always use Pydantic schemas
- ❌ Use `int` / `float` in API schemas — use `FancyInt` / `FancyFloat`
- ❌ Use `.value` on `StrEnum` / `IntEnum` — they are already `str` / `int`
- ❌ Inherit from `BaseModel` directly — use `BaseSchema` from `kactus_common.schemas`
- ❌ Import app-specific settings into `kactus-common`
- ❌ Create circular dependencies between packages
- ❌ Put business logic in `kactus-common` (infrastructure only)
- ❌ Write duplicate utilities — check `kactus-common` first
- ❌ Add `__init__.py` to test directories
- ❌ Use `config.settings` globally — use dependency injection / constructor params
- ❌ Raise bare `Exception` — use `KactusException` subclasses
- ❌ Skip tests — every feature needs tests, run `uv run pytest` before committing
- ❌ Use `import logging` / `logging.getLogger(__name__)` — use `from loguru import logger`
- ❌ Manually set `created_by` / `updated_by` — `AuditMixin` auto-populates from ContextVar
- ❌ Use `fastapi.APIRouter` — use `KactusAPIRouter` from `kactus_common.router`
- ❌ Use `Depends` for user resolution in session_routes — use `request.state.user`
