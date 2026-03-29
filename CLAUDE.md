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
- `KactusAPIRouter` auto-wraps returns in `ResponseModel`
- Return Pydantic schemas (NEVER raw dicts)
- Access user via `request.state.user` (NOT `Depends()`)
- Use `@permission(Permission.xxx, PermissionAct.write)` for authorization

### Services

- All methods as `@staticmethod` — no instance state, no `__init__`
- Dependencies passed as arguments

### Exceptions

- Subclass `KactusException` (NEVER raise bare `Exception`)
- Provide: code, title, message, tip, data
- Available: `InvalidArgumentError`, `NotFoundError`, `ConfigurationError`, `ExternalServiceError`, `DataSourceError`, …

### Logging

```python
from loguru import logger
logger.info("Processing user {user_id}", user_id=42)
```

### Settings

- Inheritance: `BaseKactusSettings → CommonSettings → DataSettings → Settings`
- Access via registry proxy: `from kactus_common.config import settings`
- Only entry-point packages load `.env` files
- Add new settings to the lowest layer that needs them:
  - Data-source API keys → `DataSettings` in `kactus_data/config.py`
  - Server config → `Settings` in `kactus_fin/config.py`
- All env vars use prefix `KACTUS_` (e.g. `KACTUS_VNAPPMOB_TOKEN`)

## Data Sources

Data sources live in `kactus-data/sources/<domain>/`. Two base classes:

| Base | Use when |
|------|---------|
| `VnstockSource` | Wrapping the vnstock Python library |
| `HttpDataSource` | Polling an external HTTP API |

All sources implement `sync(start_date, end_date, code) -> SyncDataResponse`.

### Implemented sources

| Domain | Class | Code param | Credentials |
|--------|-------|-----------|-------------|
| Stock OHLCV | `VnstockOHLCVSource` | stock symbol (e.g. `VNM`) | none |
| Stock listing | `VnstockListingSource` | `"ALL"` | none |
| Company | `VnstockCompanySource` | stock symbol | none |
| Finance | `VnstockFinanceSource` | stock symbol | none |
| VN gold | `VNAppMobGoldSource` | brand: `sjc`, `doji`, `pnj` | `KACTUS_VNAPPMOB_TOKEN` (15-day expiry) |
| Global gold | `MetalsAPISource` | metal: `XAU`, `XAG`, `XPT`, `XPD` | `KACTUS_METALS_API_KEY` |
| VN gold (legacy) | `MihongGoldSource` | brand code | XSRF token |

### DuckDB tables

All tables are defined in `sources/<domain>/tables.py` using `Table` + `Column` from `kactus_common.database.duckdb.schema`.

| Table | Primary Key | Update strategy |
|-------|-------------|-----------------|
| `stock_ohlcv` | symbol, time, interval | UPSERT |
| `stock_listing` | symbol | UPSERT |
| `stock_company` | symbol | UPSERT |
| `stock_finance` | symbol, period, year, quarter, report_type | UPSERT |
| `gold_vn` | brand, type | UPSERT |
| `gold_global` | metal, currency | UPSERT |

ALWAYS use parameterized queries — NEVER f-strings:
```python
# ✅
storage.query("SELECT * FROM gold_vn WHERE brand = ?", [brand])
# ❌
storage.query(f"SELECT * FROM gold_vn WHERE brand = '{brand}'")
```

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
| Data-source API keys | `DataSettings` in `kactus_data/config.py` |

## Adding a New Feature (Scaffold)

### API feature (kactus-fin)

1. Create `packages/kactus-fin/src/kactus_fin/<feature>/`
2. Files: `__init__.py`, `schema.py`, `service.py`, `api.py`, `app.py`
3. If you need an OLTP model: add `model.py`, register in `kactus_fin/__init__.py` `MODELS`, generate migration
4. Register `KactusApp` in `kactus_fin/app.py` via `app_manager.register(<feature>_app)`
5. Write tests in `packages/kactus-fin/tests/test_<feature>_service.py`

### Data source (kactus-data)

1. Create or extend `packages/kactus-data/src/kactus_data/sources/<domain>/`
2. Files: `__init__.py`, `<provider>.py` (subclass `HttpDataSource` or `VnstockSource`), `tables.py`
3. If new credentials needed: add field to `DataSettings` in `kactus_data/config.py`
4. Update `sources/<domain>/__init__.py` to export source + table
5. Wire into a service in kactus-fin using `SyncPipeline`

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
- ❌ F-strings in DuckDB queries — always use `?` parameterized queries
- ❌ Store API keys in code — use `.env` with `KACTUS_` prefix
