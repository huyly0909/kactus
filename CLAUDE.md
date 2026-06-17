# Kactus Monorepo

## Architecture

**uv workspaces** monorepo. Fintech platform for financial data (gold prices, stocks, financial reports).

| Package | Import As | Purpose | Port |
|---------|-----------|---------|------|
| `kactus-common` | `kactus_common` | Shared infrastructure (DB, schemas, auth, events) | - |
| `kactus-data` | `kactus_data` | Data ETL (gold, stock, finance scraping) | - |
| `kactus-fin` | `kactus_fin` | Main API server (FastAPI) | 17600 |
| `kactus-fin-gateway` | `kactus_fin_gateway` | Public API gateway (FastAPI) | 17601 |

### Dependency Flow (one-way)

```
kactus-fin  ──────┐
kactus-fin-gateway ──┤──▶ kactus-common
kactus-data  ─────┘

kactus-fin ──▶ kactus-data ──▶ kactus-common
```

Never import from app packages into `kactus-common`.

### Portfolio feature (✅ implemented)

Multi-asset watchlist (STOCK/GOLD; COIN deferred) + scheduled vnstock/mihong crawl + in-app SSE broadcast. Docs: [docs/04-portfolio-feature.md](docs/04-portfolio-feature.md) (see §16 As-built). ETL/cron/`AssetProvider` registry in `kactus-data`; API/SSE/scheduler wiring + admin in `kactus-fin` (`kactus_fin/portfolio/`); models + service + SSE broker + events in `kactus-common` (`kactus_common/portfolio/`, `kactus_common/sse/`); UI in `kactus-bloom` (`modules/portfolio/`). Portfolios are **user-owned** (ownership in service, not Casbin `@permission`). Scheduler + SSE broker are in-process → run `uvicorn --workers 1` (cờ `enable_portfolio_scheduler`; scale-out via Redis pub/sub + Celery). vnstock key via `vnai.setup_api_key()` reading `KACTUS_VNSTOCK_API_KEY` (no `validation_alias`); gold via `KACTUS_MIHONG_XSRF_TOKEN`. Blocking calls wrapped in `asyncio.to_thread`; DuckDB writes use `conn.register(df)`.

## Tech Stack

### Backend
- **Python 3.12+**, **uv** workspaces
- **FastAPI** + **SQLAlchemy 2.0 (async)** + **Pydantic v2** / **pydantic-settings**
- **PostgreSQL** (OLTP) + **DuckDB** (OLAP)
- **Alembic** migrations, **loguru** logging, **Typer** (`AsyncTyper`) CLI
- **Casbin** RBAC, **bcrypt** password hashing, **Fernet** encryption
- **pytest + pytest-asyncio** (in-memory SQLite via aiosqlite)

### Frontend (`kactus-bloom` — separate repo)
- **React 18** + **TypeScript** + **Vite 6**
- **Tailwind CSS v4** + **shadcn/ui** (Radix + CVA)
- **Zustand 5** (client state) + **TanStack Query v5** (server state)
- **i18next** (vi + en)

## Quick Commands

```bash
# Servers
python manage.py fin dev                # dev with hot-reload (port 17600)
python manage.py fin-gw dev             # gateway dev (port 17601)

# Dependencies
uv sync                                 # sync all deps

# Pre-commit
pre-commit install && pre-commit run --all-files

# Tests
uv run pytest                           # all unit tests
uv run pytest packages/kactus-fin/tests # one package
uv run pytest -k "test_login"           # by name
```

## Testing

### Unit Tests (default — fast, no Docker needed)

```bash
uv run pytest                                    # all unit tests
uv run pytest packages/kactus-common/tests       # one package
uv run pytest -k "test_login"                    # by name
```

### Coverage Gate (CI)

```bash
uv run pytest --cov --cov-fail-under=80
```

Coverage config lives in `pyproject.toml` (`[tool.coverage.*]`).

### Test Markers

| Marker | Purpose |
|--------|---------|
| `integration` | Real API tests (requires Docker) |
| `slow` | Long-running tests |
| `unit` | Unit tests |

## Skills

| Skill | Description |
|-------|-------------|
| `project-conventions` | Architecture, coding conventions, guardrails |
| `coding-conventions` | Import rules, typing, schema/model patterns |
| `api-conventions` | KactusAPIRouter, response patterns, DB access |
| `database-migration` | Alembic workflow, model checklist |
| `feature-scaffold` | Step-by-step feature creation |
| `model-registration` | MODELS, INSTALLED_PACKAGES, load_models() |
| `testing` | pytest patterns, fixtures, test organization |
| `cli-command` | AsyncTyper, command registration |

## Workflows

| Workflow | Description |
|----------|-------------|
| `/add-feature` | Step-by-step guide for adding a new feature |

## Docker Environments

```bash
cd packages/docker-hub/{env}
docker compose up -d

# Migrations
docker compose exec kactus-fin python manage.py fin db upgrade
```

## Don't Do This

- ❌ Import inside functions/methods — always at top of file
- ❌ Use `Union[A, B]`, `Optional[X]`, `Dict`, `List` — use `A | B`, `X | None`, `dict`, `list`
- ❌ Return raw dicts from API endpoints — always use Pydantic schemas
- ❌ Use `int` / `float` in API schemas — use `FancyInt` / `FancyFloat`
- ❌ Inherit from `BaseModel` directly — use `BaseSchema`
- ❌ Import app-specific code into `kactus-common`
- ❌ Create circular dependencies between packages
- ❌ Put business logic in `kactus-common` (infrastructure only)
- ❌ Use `fastapi.APIRouter` — use `KactusAPIRouter`
- ❌ Use `import logging` — use `from loguru import logger`
- ❌ Skip tests — every feature needs tests, run `uv run pytest` before committing
- ❌ Manually set `created_by` / `updated_by` — `AuditMixin` auto-populates from ContextVar
