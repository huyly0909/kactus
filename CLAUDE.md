# Kactus Monorepo

## Architecture

**uv workspaces** monorepo. Fintech platform for financial data (gold prices, stocks, financial reports).

Directories express the layering: **`services/` sits above `libs/`, which sits above `libs/core/`.**
Deeper = lower layer, and a lower layer never imports upward.

| Path | Package | Import As | Purpose | Port |
|------|---------|-----------|---------|------|
| `libs/core/kactus-common` | `kactus-common` | `kactus_common` | Shared infrastructure (DB, schemas, auth, events) | - |
| `libs/kactus-data` | `kactus-data` | `kactus_data` | Data ETL (gold, stock, finance scraping) | - |
| `services/kactus-fin` | `kactus-fin` | `kactus_fin` | Main API server (FastAPI) | 17600 |
| `services/kactus-fin-gateway` | `kactus-fin-gateway` | `kactus_fin_gateway` | Public API gateway (FastAPI) | 17601 |
| `deploy/` | - | - | Dockerfiles + per-env compose (not a Python package) | - |

`services/` are the only deployable units; nothing imports *into* them.

### Dependency Flow (one-way)

```
services/kactus-fin ────────┐
services/kactus-fin-gateway ─┤──▶ libs/core/kactus-common
libs/kactus-data ───────────┘

services/kactus-fin ──▶ libs/kactus-data ──▶ libs/core/kactus-common
```

Never import from app packages into `kactus-common`.

**This is enforced, not just documented.** The layer contract lives in
`pyproject.toml` (`[tool.importlinter]`); run `uv run lint-imports` — it fails the
build on an upward import. Directory depth alone enforces nothing (Python import
does not care), which is why the contract exists.

### Portfolio feature (✅ implemented)

Multi-asset watchlist (STOCK/GOLD; COIN deferred) + scheduled vnstock/mihong crawl + in-app SSE broadcast. Docs: [docs/04-portfolio-feature.md](docs/04-portfolio-feature.md) (see §16 As-built). ETL/cron/`AssetProvider` registry in `kactus-data`; API/SSE/scheduler wiring + admin in `kactus-fin` (`kactus_fin/portfolio/`); models + service + SSE broker + events in `kactus-common` (`kactus_common/portfolio/`, `kactus_common/sse/`); UI in `kactus-bloom` (`modules/portfolio/`). Portfolios are **user-owned** (ownership in service, not Casbin `@permission`). Scheduler + SSE broker are in-process → run `uvicorn --workers 1` (cờ `enable_portfolio_scheduler`; scale-out via Redis pub/sub + Celery). vnstock key via `vnai.setup_api_key()` reading `KACTUS_VNSTOCK_API_KEY` (no `validation_alias`). **Gold quotes need no credential**: `SjcGoldSource` (sjc.com.vn, authoritative SJC reference, Cloudflare → `curl_cffi impersonate=chrome`) is tried first and `MihongGoldSource` (api.mihong.vn, `last=` trailing window) is the fallback — `KACTUS_MIHONG_XSRF_TOKEN` is legacy/unused. World gold (`XAU`) comes from `YahooGoldSource` (`GC=F` — `XAUUSD=X` is delisted; explicit `period1`/`period2` + `interval=1d`, since `range=max` degrades to monthly). `gold_price_board` therefore mixes units and every row carries an explicit **`unit`** (`VND/luong` vs `USD/oz`) — never assume VND. `DOJI`/`PNJ` stay in the catalog flagged `enabled: false` + tag `disabled` (no free feed wired). Source research + one-off history backfill scripts live in `labenry-lab/gold/`. Blocking calls wrapped in `asyncio.to_thread`; DuckDB writes use `conn.register(df)`.

### OLAP money columns & schema drift

**Every price/money column in DuckDB is `DECIMAL`** (`DataType.DECIMAL` → `DECIMAL(24,4)` via `Column.sql_type`; override with `precision`/`scale`). `FLOAT` is single-precision and exact only below 2^24 (~16.7M), so it silently rounds VND gold (~1.4e8) and share counts (~1e9) — those non-money counts/volumes are `DOUBLE`. Money stays a `Decimal` end to end: DECIMAL column → `Decimal` in Python → JSON string via **`FancyDecimal`** (`FancyFloat` would coerce back to float and throw the precision away). Mind `Decimal * float` → `TypeError` in any derived arithmetic.

DuckDB has no Alembic: tables are created with `CREATE TABLE IF NOT EXISTS`, so **editing a `Table` definition never reaches an existing database**, and because inserts are positional (`SELECT *` over a registered df) drift misaligns columns rather than erroring cleanly. Register every table in `kactus_data/sources/registry.py`, then:

```bash
python manage.py data schema check              # diff definitions vs the live file
python manage.py data schema recreate [table]   # DROP + rebuild (destroys rows; re-run the crawl)
```

### Notification feature (✅ implemented)

Multi-channel push (Telegram/Slack/**Zalo PA**) as shared infra in `kactus-common` (`kactus_common/notification/`). Docs: [docs/06-notification-feature.md](docs/06-notification-feature.md). **One shared `NotificationChannel` "connection" for every platform** — `channel_type` + a `config: dict` on an **`EncryptedJSON`** (Fernet) column, each platform coerced by a per-type Pydantic schema (`TelegramChannelConfig`/`SlackChannelConfig`/`ZaloPAChannelConfig`) via `CHANNEL_CONFIG_SCHEMAS`; secrets masked by `SECRET_FIELDS`+`mask_config`. **No separate Zalo table.** Channels are **user-owned** (ownership in service). Adding a channel type = +1 config schema, +1 `*Channel`, +1 `*EventTemplate`, +1 entry in each registry. `Notifier.send_event(session, channel, event, *, trigger=MANUAL)` renders (per-type template) + delivers via `asyncio.to_thread`, with **synchronous bounded retry** (`notification_max_send_attempts=3`, exp backoff) on `impl.retryable_exceptions` — deterministic `ExternalServiceError` is **not** retried — and writes a `NotificationLog` (append-only audit, mirror `CrawlRun`) on every outcome. **Push-only** (no inbound/webhook). HTTP in `kactus_fin/notification/` (`api.py` generic CRUD/test/send/`GET /{id}/logs`; `zalo_pa_api.py` QR + zalo channel create/reauth). **Zalo PA** = unofficial personal account via PyPI `zlapi` (sync→`to_thread`), 5-step QR login (`zalo_pa.py`, `curl_cffi impersonate=chrome`) held in an **in-process TTL session store** (single-worker → `uvicorn --workers 1`); session lives inside `ZaloPAChannelConfig` (encrypted); recipients from `fetchAllFriends`/`fetchAllGroups`; **residential proxy** (`KACTUS_ZALO_PA_PROXY_URL`) required non-dev; **account-suspension risk**; expired session → non-retryable. UI in `kactus-bloom` (`modules/notification/`). Event-driven auto-fire is **deferred** (`trigger=EVENT` already threaded through the log).

### Market feature (✅ implemented)

Read-only REST over the **OLAP (DuckDB)** tables the kactus-data ETL writes — no new ETL, no new tables. Lives in `kactus_fin/market/` (`const`/`schema`/`service`/`api`/`app`), registered as `KactusApp(name="market", session_routes=[router])` — session auth, no Casbin/ownership (market data is reference data). Endpoints: `GET /api/market/gold`, `/stocks` (search), `/stocks/quotes`, `/stocks/{symbol}`, `/stocks/{symbol}/ohlcv`, `/stocks/{symbol}/news`, `/stocks/{symbol}/finance`. Reads go through **one process-wide `DuckDBStorage`** published by the lifespan in `kactus_fin/olap.py` (`get_olap_storage()`) — never construct a second handle on the same file. Blocking DuckDB calls are wrapped in `asyncio.to_thread`; caller values are bound as **positional params** (`DuckDBStorage.query(sql, params)`), never interpolated; limits are capped (`MAX_LIMIT=2000`); a table the ETL has not created yet reads as `[]`, not a 500. UI in `kactus-bloom` (`modules/market/`: gold board, stock list + detail with recharts price history + news, finance pivot). Market pages are **poll-on-navigate** (no SSE — that is portfolio-only).

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

# Dependencies — plain `uv sync` only syncs the root project and PRUNES the
# workspace members' deps, which breaks the venv. Always pass --all-packages.
uv sync --all-packages                  # sync all deps

# Pre-commit
pre-commit install && pre-commit run --all-files

# Layer contract (services -> libs -> core)
uv run lint-imports

# Tests
uv run pytest                           # all unit tests
uv run pytest services/kactus-fin/tests # one package
uv run pytest -k "test_login"           # by name
```

## Testing

### Unit Tests (default — fast, no Docker needed)

```bash
uv run pytest                                    # all unit tests
uv run pytest libs/core/kactus-common/tests       # one package
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
cd deploy/{env}
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
