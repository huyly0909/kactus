# Kactus Backend — Claude Code Instructions

## Architecture

**uv workspaces** monorepo with 5 packages:

| Package | Import As | Purpose | Port |
|---------|-----------|---------|------|
| `kactus-common` | `kactus_common` | Shared infrastructure — DB clients, schemas, events, logging, exceptions | — |
| `kactus-data` | `kactus_data` | Data processing, scraping, ETL pipelines | — |
| `kactus-fin` | `kactus_fin` | FastAPI backend server (main API) | 17600 |
| `kactus-fin-gateway` | `kactus_fin_gateway` | FastAPI gateway server (public APIs) | 17601 |
| `docker-hub` | — | Docker Compose configs for dev/stag/prod | — |

### Dependency Flow (One-Way — NEVER reverse)

```
kactus-fin  ──────┐
kactus-fin-gateway ──┤──▶ kactus-common
kactus-data  ─────┘
```

## Tech Stack

- **Python 3.12+** / **uv** workspaces
- **FastAPI** + **SQLAlchemy 2.0 async** + **Pydantic v2** / **pydantic-settings**
- **DuckDB** (OLAP) / **PostgreSQL** (OLTP via SQLAlchemy) / **Alembic** (migrations)
- **loguru** for logging (NEVER `import logging`)
- **Typer** (`AsyncTyper`) for CLI
- **pytest + pytest-asyncio + aiosqlite** for testing (in-memory SQLite)
- **pre-commit**: isort, autoflake, black, flake8

## Coding Conventions

### Typing — Modern Python 3.12+

```python
# ✅ Correct
def process(items: list[str], config: dict[str, int] | None = None) -> str | None: ...

# ❌ NEVER: Union[A, B], Optional[X], Dict, List from typing
```

### Imports — Full Package Paths Only

```python
# ✅
from kactus_common.database.duckdb.client import DatabaseClient
from kactus_common.database.oltp.session import get_db
from kactus_common.exceptions import NotFoundError
from kactus_common.schemas import BaseSchema

# ❌ NEVER use relative imports across packages
```

### Schemas (Pydantic)

- Always inherit `BaseSchema` (NOT `BaseModel` directly)
- Use `FancyInt` / `FancyFloat` for numeric fields in API responses (avoids JS precision loss)
- `BaseSchema` provides: whitespace stripping, empty-string-to-None, `from_attributes=True`

### OLTP Models (SQLAlchemy)

```python
from kactus_common.database.oltp.models import Base, ModelMixin, AuditMixin, LogicalDeleteMixin

class User(Base, ModelMixin, AuditMixin, LogicalDeleteMixin):
    __tablename__ = "users"
    name: Mapped[str] = mapped_column()
```

- `ModelMixin` → snowflake `id`, `create_time`, `update_time`
- `AuditMixin` → `created_by`, `updated_by` (auto-populated from ContextVar — NEVER set manually)
- `LogicalDeleteMixin` → soft-delete via `deleted_timestamp`

### Database Access

```python
from kactus_common.database.oltp.session import get_db
async with get_db().get_session() as session:
    user = await User.get_or_404(session, user_id)
```

### API Endpoints

- Use `KactusAPIRouter` from `kactus_common.router` (NOT `fastapi.APIRouter`)
- KactusAPIRouter auto-wraps returns in `ResponseModel`
- Return Pydantic schemas (NEVER raw dicts)
- Access user via `request.state.user` (NOT `Depends()`)
- Use `@permission(Permission.xxx, PermissionAct.write)` for authorization

### Services

- All methods as `@staticmethod` — no instance state, no `__init__`
- Dependencies passed as arguments

### Exceptions

- Subclass `KactusException` (NEVER raise bare `Exception`)
- Provide: code, title, message, tip, data

### Logging

```python
from loguru import logger
logger.info("Processing user {user_id}", user_id=42)
```

### Settings

- Inheritance: `BaseKactusSettings → CommonSettings → DataSettings → Settings`
- Access via registry proxy: `from kactus_common.config import settings`
- Only entry-point packages load `.env` files

## Where to Put Code

| You need to... | Put it in... |
|----------------|-------------|
| Shared feature (user, auth) | `kactus-common/<feature>/` |
| App-specific feature | `<app-package>/<feature>/` |
| Shared infra (DB, events) | `kactus-common/` top-level |
| New exception type | `kactus_common/exceptions.py` |
| Data source / scraper | `kactus-data/sources/<domain>/` |
| ETL job | `kactus-data/jobs/` |
| API endpoint (main) | `kactus-fin/<feature>/api.py` |
| API endpoint (gateway) | `kactus-fin-gateway/api/` |

## Adding a New Feature (Scaffold)

1. Create directory: `<package>/<feature>/`
2. Files: `const.py`, `model.py`, `schema.py`, `service.py`, `api.py`, `app.py`
3. Register model in package `__init__.py` `MODELS` list
4. Register app in main `app.py` via `AppManager`
5. Add to `Settings.INSTALLED_PACKAGES`
6. Generate migration: `python manage.py fin db migrate -m "add <feature>"`
7. Write tests

## Model Registration (Critical)

1. Package `__init__.py`: `MODELS = ["pkg.feature.model"]`
2. Settings: `INSTALLED_PACKAGES: ClassVar[list[str]] = Parent.INSTALLED_PACKAGES + ["pkg"]`
3. Alembic `env.py`: `load_models(settings)` before `target_metadata` — NEVER remove this

## Commands

```bash
# Dev servers
python manage.py fin dev              # port 17600
python manage.py fin-gw dev           # port 17601

# Tests
uv run pytest                                        # all tests
uv run pytest packages/kactus-fin/tests              # single package
uv run pytest -k "test_login"                        # filter by name
uv run pytest -m "not slow"                          # exclude slow

# Migrations
python manage.py fin db migrate -m "message"
python manage.py fin db upgrade

# Dependencies
cd packages/kactus-common && uv add <package>
uv sync --all-packages
```

## Don'ts

- ❌ `Union`, `Optional`, `Dict`, `List` from typing — use `A | B`, `X | None`, `dict`, `list`
- ❌ Return raw dicts from API — use Pydantic schemas
- ❌ `int`/`float` in API schemas — use `FancyInt`/`FancyFloat`
- ❌ `.value` on `StrEnum`/`IntEnum` — they are already `str`/`int`
- ❌ `BaseModel` directly — use `BaseSchema`
- ❌ Import downstream into `kactus-common` (circular deps)
- ❌ Business logic in `kactus-common` (infra only)
- ❌ `__init__.py` in test directories
- ❌ `fastapi.APIRouter` — use `KactusAPIRouter`
- ❌ `Depends()` for user — use `request.state.user`
- ❌ `import logging` — use `from loguru import logger`
- ❌ Manually set `created_by`/`updated_by` — `AuditMixin` auto-populates
- ❌ Skip tests — every feature needs tests
