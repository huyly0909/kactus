# Kactus Monorepo

## Architecture

**uv workspaces** monorepo. Fintech platform for financial data (gold prices, stocks, financial reports).

Directories express the layering: **`services/` sits above `libs/`, which sits above `libs/core/`.**
Deeper = lower layer, and a lower layer never imports upward.

| Path | Package | Import As | Purpose | Port |
|------|---------|-----------|---------|------|
| `libs/core/kactus-common` | `kactus-common` | `kactus_common` | Shared infrastructure (DB, schemas, auth, events) | - |
| `libs/kactus-data` | `kactus-data` | `kactus_data` | Data ETL (gold, stock, finance scraping) | - |
| `libs/kactus-notification` | `kactus-notification` | `kactus_notification` | Notification domain (channels, templates, delivery) | - |
| `services/kactus-fin` | `kactus-fin` | `kactus_fin` | Main API server — **control plane** (FastAPI) | 17600 |
| `services/kactus-fin-gateway` | `kactus-fin-gateway` | `kactus_fin_gateway` | Public API gateway (FastAPI) | 17601 |
| `services/kactus-data-server` | `kactus-data-server` | `kactus_data_server` | ETL + DuckDB + crawl scheduler — **data plane** (FastAPI) | 17602 |
| `deploy/` | - | - | Dockerfiles + per-env compose (not a Python package) | - |

`services/` are the only deployable units; nothing imports *into* them.

### Dependency Flow (one-way)

```
services/kactus-fin ────────┐
services/kactus-fin-gateway ─┤──▶ libs/core/kactus-common
services/kactus-data-server ─┤
libs/kactus-data ───────────┤
libs/kactus-notification ───┘

services/kactus-data-server ──▶ libs/kactus-data         ──▶ libs/core/kactus-common
services/kactus-fin         ──▶ libs/kactus-notification ──▶ libs/core/kactus-common

services/kactus-fin ──HTTP──▶ services/kactus-data-server   (no import, ever)
```

`kactus-data` and `kactus-notification` are **siblings** — neither imports the
other. `kactus-fin` **no longer imports `kactus-data` at all**: a second
`forbidden` contract (`kactus_fin` ✗→ `kactus_data`, `duckdb`) fails the build if
the dependency comes back, because the layered contract alone would allow it.

Never import from app packages into `kactus-common`.

**This is enforced, not just documented.** The layer contract lives in
`pyproject.toml` (`[tool.importlinter]`); run `uv run lint-imports` — it fails the
build on an upward import. Directory depth alone enforces nothing (Python import
does not care), which is why the contract exists.

### Redis — coordination only

`kactus_common/redis/` (`client` pool + `namespaced()`, `lock`, `cache`). Redis
coordinates **processes**; it is never a source of truth and never a job queue.

| Concern | Where | Why |
|---|---|---|
| Audit (`CrawlRun`, `NotificationLog`) | **Postgres** | Redis can be flushed or lost on failover |
| Commands between services | **HTTP** | status codes, timeouts, tracing |
| Event fan-out that may be dropped (SSE nudges) | **Redis pub/sub** | client refetches; loss is harmless |
| Delivery that must **not** be dropped | **Redis Streams** (not built yet) | pub/sub does not persist |
| Locks, cache, TTL session stores | **Redis + TTL** | what it is for |

One switch governs it: **`KACTUS_COORDINATION_BACKEND`** (`memory` | `redis`),
covering both the SSE broker and the Zalo QR session store. Deliberately not two
knobs — enabling one and forgetting the other breaks QR login in a way nothing
reports. `redis` also requires `KACTUS_ENCRYPTION_KEY` (Zalo sessions are
Fernet-encrypted before they are written). `memory` is correct only at
`--workers 1`. There is **no** silent fallback: an unreachable Redis on the
`redis` backend surfaces as `{"status": "degraded"}` on `/health`.

Every key goes through `namespaced()` so one Redis can host several
environments. `cache_*` degrades to a miss on failure — a cache outage must not
become a 500. `distributed_lock` releases with a compare-and-delete Lua script,
so an expired holder cannot delete the next holder's lock.

### Data plane / control plane split (✅ implemented)

`services/kactus-data-server` (port 17602) owns the **DuckDB write handle**, the
`AssetProvider` registry, vnstock auth and the crawl `AsyncIOScheduler`.
`kactus-fin` owns users, portfolios, authorization and the browser-facing API,
and reaches market data over HTTP through `kactus_fin/data_client.py`.

DuckDB permits one read-write process **or** several read-only ones, never both
across processes — so there is no "read it directly, just this once" option. That
is the real cost of the split, and it is paid in `data_client.py`.

| Surface | Data plane | Replaces |
|---|---|---|
| `GET /internal/market/*` | 7 endpoints | the 7 `MarketService` reads |
| `GET /internal/assets/{asset_type}/{kind}?code=` | 1 endpoint | all 3 `provider.read(...)` call sites |
| `POST /internal/crawl`, `/internal/catalog/sync` | queue + return | `background.add_task(run_crawl, ...)` |
| `GET /internal/scheduler/status` | scheduler snapshot | the scheduler half of `crawl_status` |

Rules that hold the split together:

- **Commands over HTTP, events over Redis, audit in Postgres.** A crawl trigger
  has a caller who wants a status code; the SSE nudge is fire-and-forget.
- **`/internal` requires `X-Service-Token`** (`KACTUS_INTERNAL_SERVICE_TOKEN`,
  `hmac.compare_digest`), and an **unset** token fails every request rather than
  making the surface anonymous. Health is the one unauthenticated route.
- **No per-user authorization on the data plane.** Ownership rules live in
  kactus-fin, in one place; what reaches the data plane is already authorized.
- **The data plane returns `null`/`[]`, never 404.** Whether an unknown symbol is
  an error is a product decision, and it stays with the user-facing message.
- **The in-flight crawl guard stays in kactus-fin** — same Postgres, so a
  duplicate refresh costs no round trip.
- `kactus-data-server` runs **1 worker, 1 replica, permanently** and ships **no
  Alembic** (no ORM models of its own; it shares kactus-fin's migration head).

### Portfolio feature (✅ implemented)

Multi-asset watchlist (STOCK/GOLD; COIN deferred) + scheduled vnstock/mihong crawl + in-app SSE broadcast. Docs: [docs/04-portfolio-feature.md](docs/04-portfolio-feature.md) (see §16 As-built). ETL/cron/`AssetProvider` registry in `kactus-data`; API/SSE/scheduler wiring + admin in `kactus-fin` (`kactus_fin/portfolio/`); models + service + SSE broker + events in `kactus-common` (`kactus_common/portfolio/`, `kactus_common/sse/`); UI in `kactus-bloom` (`modules/portfolio/`). Portfolios are **user-owned** (ownership in service, not Casbin `@permission`). SSE fan-out goes through the **Redis broker** (`coordination_backend=redis`) and the scheduler now lives in `kactus-data-server`, so **`kactus-fin` is multi-worker again** (4 in prod, 2 in stag); the single-worker constraint moved with the scheduler (cờ `enable_portfolio_scheduler` is now the data plane's). vnstock key via `vnai.setup_api_key()` reading `KACTUS_VNSTOCK_API_KEY` (no `validation_alias`). **Gold quotes need no credential**: `SjcGoldSource` (sjc.com.vn, authoritative SJC reference, Cloudflare → `curl_cffi impersonate=chrome`) is tried first and `MihongGoldSource` (api.mihong.vn, `last=` trailing window) is the fallback — `KACTUS_MIHONG_XSRF_TOKEN` is legacy/unused. World gold (`XAU`) comes from `YahooGoldSource` (`GC=F` — `XAUUSD=X` is delisted; explicit `period1`/`period2` + `interval=1d`, since `range=max` degrades to monthly). `gold_price_board` therefore mixes units and every row carries an explicit **`unit`** (`VND/luong` vs `USD/oz`) — never assume VND. `DOJI`/`PNJ` stay in the catalog flagged `enabled: false` + tag `disabled` (no free feed wired). Source research + one-off history backfill scripts live in `labenry-lab/gold/`. Blocking calls wrapped in `asyncio.to_thread`; DuckDB writes use `conn.register(df)`.

### OLAP money columns & schema drift

**Every price/money column in DuckDB is `DECIMAL`** (`DataType.DECIMAL` → `DECIMAL(24,4)` via `Column.sql_type`; override with `precision`/`scale`). `FLOAT` is single-precision and exact only below 2^24 (~16.7M), so it silently rounds VND gold (~1.4e8) and share counts (~1e9) — those non-money counts/volumes are `DOUBLE`. Money stays a `Decimal` end to end: DECIMAL column → `Decimal` in Python → JSON string via **`FancyDecimal`** (`FancyFloat` would coerce back to float and throw the precision away). Mind `Decimal * float` → `TypeError` in any derived arithmetic.

DuckDB has no Alembic: tables are created with `CREATE TABLE IF NOT EXISTS`, so **editing a `Table` definition never reaches an existing database**, and because inserts are positional (`SELECT *` over a registered df) drift misaligns columns rather than erroring cleanly. Register every table in `kactus_data/sources/registry.py`, then:

```bash
python manage.py data schema check              # diff definitions vs the live file
python manage.py data schema recreate [table]   # DROP + rebuild (destroys rows; re-run the crawl)
```

### Notification feature (✅ implemented)

Multi-channel push (Telegram/Slack/**Zalo PA**) as its own library, `libs/kactus-notification` (`kactus_notification/`) — a **sibling of `kactus-data`, not part of `kactus-common`**: channel registry, template rendering, retry policy and QR login are domain logic, and keeping the unofficial `zlapi` down in the core layer forced it onto every consumer (the gateway included, which never sends anything). Settings come from `NotificationSettings`, a mixin merged in by `kactus_fin.config.Settings` — a service that does not send notifications simply does not mix it in. Docs: [docs/06-notification-feature.md](docs/06-notification-feature.md). **One shared `NotificationChannel` "connection" for every platform** — `channel_type` + a `config: dict` on an **`EncryptedJSON`** (Fernet) column, each platform coerced by a per-type Pydantic schema (`TelegramChannelConfig`/`SlackChannelConfig`/`ZaloPAChannelConfig`) via `CHANNEL_CONFIG_SCHEMAS`; secrets masked by `SECRET_FIELDS`+`mask_config`. **No separate Zalo table.** Channels are **user-owned** (ownership in service). Adding a channel type = +1 config schema, +1 `*Channel`, +1 `*EventTemplate`, +1 entry in each registry. `Notifier.send_event(session, channel, event, *, trigger=MANUAL)` renders (per-type template) + delivers via `asyncio.to_thread`, with **synchronous bounded retry** (`notification_max_send_attempts=3`, exp backoff) on `impl.retryable_exceptions` — deterministic `ExternalServiceError` is **not** retried — and writes a `NotificationLog` (append-only audit, mirror `CrawlRun`) on every outcome. **Push-only** (no inbound/webhook). HTTP in `kactus_fin/notification/` (`api.py` generic CRUD/test/send/`GET /{id}/logs`; `zalo_pa_api.py` QR + zalo channel create/reauth). **Zalo PA** = unofficial personal account via PyPI `zlapi` (sync→`to_thread`), 5-step QR login (`zalo_pa.py`, `curl_cffi impersonate=chrome`) held in a **TTL session store** — in-process, or in Redis (Fernet-encrypted, `KACTUS_ENCRYPTION_KEY` required) when `coordination_backend=redis`, which lets the 5 steps land on different workers; the store interface is **async** (`await get_session_store().load(...)`); session lives inside `ZaloPAChannelConfig` (encrypted); recipients from `fetchAllFriends`/`fetchAllGroups`; **residential proxy** (`KACTUS_ZALO_PA_PROXY_URL`) required non-dev; **account-suspension risk**; expired session → non-retryable. UI in `kactus-bloom` (`modules/notification/`). Event-driven auto-fire is **deferred** (`trigger=EVENT` already threaded through the log).

### Market feature (✅ implemented)

Read-only REST over the **OLAP (DuckDB)** tables the kactus-data ETL writes — no new ETL, no new tables. Lives in `kactus_fin/market/` (`api`/`app` only — `const`/`schema` moved up to `kactus_common/market/` so both planes share them, and `service.py` moved down to `kactus_data/market/`), registered as `KactusApp(name="market", session_routes=[router])` — session auth, no Casbin/ownership (market data is reference data). Endpoints: `GET /api/market/gold`, `/stocks` (search), `/stocks/quotes`, `/stocks/{symbol}`, `/stocks/{symbol}/ohlcv`, `/stocks/{symbol}/news`, `/stocks/{symbol}/finance`. After the data-plane split, `kactus_fin/market/api.py` is a thin forwarder: each endpoint awaits the matching `data_client` call. `MarketService` and the one process-wide `DuckDBStorage` now live in `kactus-data-server` (`DataRuntime.storage`) — never construct a second handle on the same file, in any process. Blocking DuckDB calls are wrapped in `asyncio.to_thread`; caller values are bound as **positional params** (`DuckDBStorage.query(sql, params)`), never interpolated; limits are capped (`MAX_LIMIT=2000`); a table the ETL has not created yet reads as `[]`, not a 500. UI in `kactus-bloom` (`modules/market/`: gold board, stock list + detail with recharts price history + news, finance pivot). Market pages are **poll-on-navigate** (no SSE — that is portfolio-only).

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
python manage.py data-server dev        # data plane (port 17602) — needs the
                                        # same KACTUS_INTERNAL_SERVICE_TOKEN

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
