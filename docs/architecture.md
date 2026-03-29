# Kactus Backend — Architecture

## Overview

Kactus is a **uv workspaces** Python monorepo. The backend serves financial data (Vietnamese stocks and gold prices) via a FastAPI HTTP API. Data is fetched from external providers, cached in DuckDB (OLAP), and served through the API. User accounts, projects, and auth are stored in PostgreSQL (OLTP).

```
┌───────────────────────────────────────────────────────────────┐
│                     kactus-bloom (React)                      │
│                      port 17630                               │
└────────────────────────────┬──────────────────────────────────┘
                             │ HTTP
                             ▼
┌───────────────────────────────────────────────────────────────┐
│                   kactus-fin (FastAPI)                        │
│                     port 17600                                │
│                                                               │
│  /api/stock        /api/company     /api/finance              │
│  /api/gold/vn      /api/gold/global /api/auth   ...           │
└──────┬──────────────────────────────────────────┬────────────┘
       │                                          │
       ▼                                          ▼
┌─────────────────────┐              ┌────────────────────────┐
│  kactus-data        │              │  kactus-common         │
│  (ETL + storage)    │              │  (shared infra)        │
│                     │              │                        │
│  Data Sources:      │              │  PostgreSQL (OLTP)     │
│  ├─ Vnstock         │              │  ├─ users              │
│  ├─ VNAppMob Gold   │              │  ├─ projects           │
│  ├─ Metals-API      │              │  └─ sessions           │
│  └─ (fallbacks)     │              │                        │
│                     │              │  Shared:               │
│  DuckDB (OLAP)      │              │  ├─ KactusAPIRouter     │
│  ├─ stock_ohlcv     │              │  ├─ BaseSchema          │
│  ├─ stock_listing   │              │  ├─ KactusException     │
│  ├─ stock_company   │              │  ├─ AppManager          │
│  ├─ stock_finance   │              │  └─ auth / permissions  │
│  ├─ gold_vn         │              └────────────────────────┘
│  └─ gold_global     │
└─────────────────────┘
```

---

## Package Responsibilities

### kactus-common

Shared infrastructure only — no business logic.

- **Router** — `KactusAPIRouter` auto-wraps endpoint returns in `ResponseModel[T]`
- **Schemas** — `BaseSchema`, `ResponseModel`, `Pagination`, `FancyInt`, `FancyFloat`
- **Exceptions** — `KactusException` hierarchy (maps to HTTP status codes)
- **OLTP database** — SQLAlchemy 2.0 async session management, base models with mixins
- **OLAP database** — `DatabaseClient` (DuckDB), `Table`/`Column` schema definitions
- **Auth** — session cookie auth, permission system (Casbin)
- **Config** — `BaseKactusSettings` → `CommonSettings` base for all packages
- **App registry** — `KactusApp` + `AppManager` for wiring features into FastAPI

### kactus-data

Data acquisition and ETL. No HTTP servers, no FastAPI.

- **Sources** — pluggable data source classes, one per provider
- **Pipeline** — `SyncPipeline`: fetch → transform → store into DuckDB
- **Storage** — `DuckDBStorage` high-level wrapper around `DatabaseClient`
- **Config** — `DataSettings(CommonSettings)` adds data-source credentials

### kactus-fin

Main API server. Owns all user-facing API endpoints.

- One directory per domain: `stock/`, `company/`, `finance/`, `gold/`, `auth/`, `project/`, …
- Each domain: `schema.py` + `service.py` + `api.py` + `app.py`
- Services call kactus-data sources/storage; never import from kactus-fin-gateway
- All routes are superuser-protected (auth via session cookie)

### kactus-fin-gateway

Public-facing gateway (port 17601). Proxies or re-exposes a subset of kactus-fin endpoints without requiring superuser auth.

---

## Request Lifecycle

```
1. Request arrives at kactus-fin (port 17600)
2. SecurityHeadersMiddleware adds response headers
3. CORSMiddleware checks origin against settings.cors_allowed_origins
4. AppManager routes to the matching feature router
5. Auth dependency (_session_auth or _superuser_auth) validates session cookie
6. Endpoint handler calls Service static method
7. Service calls DuckDBStorage.query() with parameterized SQL
8. KactusAPIRouter wraps return value: ResponseModel(data=result)
9. JSON response sent to client
```

---

## Data Sync Lifecycle

```
1. POST /api/gold/vn/sync (or any /sync endpoint)
2. Service creates DataSource + SyncPipeline
3. SyncPipeline.run():
   a. source.sync(start_date, end_date, code) → SyncDataResponse
   b. Transform response data to pd.DataFrame
   c. Reorder columns to match Table definition
   d. DuckDBStorage.store(table, df, UpdateStrategy.UPSERT)
4. Return SyncResult(rows_fetched, rows_stored, duration_ms, …)
```

---

## Database Design

### OLTP (PostgreSQL via SQLAlchemy)

Transactional data with strong consistency requirements:

| Table | Purpose |
|-------|---------|
| `users` | User accounts (hashed passwords, superuser flag) |
| `sessions` | Auth session cookies |
| `projects` | Workspace/project isolation |
| `project_members` | User ↔ project membership + roles |
| `permissions` | Casbin policy rows |

All models use `ModelMixin` (snowflake id, timestamps) and `AuditMixin` (created_by, updated_by via ContextVar).

### OLAP (DuckDB)

Append-heavy analytical data, queried read-mostly:

| Table | Primary Key | Source | TTL |
|-------|-------------|--------|-----|
| `stock_ohlcv` | symbol, time, interval | Vnstock | — (historical) |
| `stock_listing` | symbol | Vnstock | Refresh daily |
| `stock_company` | symbol | Vnstock | Refresh on demand |
| `stock_finance` | symbol, period, year, quarter, report_type | Vnstock | Refresh on demand |
| `gold_vn` | brand, type | VNAppMob API | Refresh every 5–15 min |
| `gold_global` | metal, currency | Metals-API | Refresh every 1–5 min |

DuckDB lives at the path set by `KACTUS_DB_PATH` (default: `kactus.duckdb`).

---

## Settings Hierarchy

```
BaseKactusSettings          app_env, debug, log_level
  └─ CommonSettings         database_url, db_path, cors_allowed_origins, session config
       └─ DataSettings      data_source, vnappmob_token, metals_api_key
            └─ Settings     app_name, host, port  ← only this loads .env
```

All env vars use `KACTUS_` prefix. Only `kactus-fin/config.py` loads `.env`; all parent fields are populated from it.

Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `KACTUS_APP_ENV` | `dev` | `dev` / `stag` / `prod` |
| `KACTUS_DATABASE_URL` | — | PostgreSQL connection string |
| `KACTUS_DB_PATH` | `kactus.duckdb` | DuckDB file path |
| `KACTUS_CORS_ALLOWED_ORIGINS` | `http://localhost:17630` | Allowed frontend origins |
| `KACTUS_VNAPPMOB_TOKEN` | — | VNAppMob API bearer token (15-day expiry) |
| `KACTUS_METALS_API_KEY` | — | Metals-API API key |

---

## Security Model

- **Auth**: Session cookies (Fernet-encrypted), set on login, validated per request
- **Authorization**: Casbin RBAC — roles scoped to projects
- **Superuser**: Bypasses all Casbin checks; all data-sync endpoints require superuser
- **CORS**: Explicit allowlist — wildcard `*` is banned (CLAUDE.md rule)
- **SQL injection**: All DuckDB queries use `?` parameterized queries — f-strings are banned
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, HSTS in prod

---

## Feature Registration Pattern

Every domain feature is wired into FastAPI via `KactusApp`:

```python
# gold/app.py
from kactus_common.app_registry import KactusApp
from kactus_fin.gold.api import router

gold_app = KactusApp(
    name="gold",
    superuser_routes=[router],   # requires superuser auth
    # session_routes=[...]       # requires session auth only
    # public_routes=[...]        # no auth
)

# app.py
app_manager.register(gold_app)
```

`AppManager.init_fastapi(app)` wires all registered apps into the FastAPI instance at startup.

---

## External Data Providers

| Provider | Domain | Free | Auth | Notes |
|----------|--------|------|------|-------|
| Vnstock | VN stocks | ✅ | None (guest) | Python library wrapping TCBS/SSI/KBS |
| VNAppMob Gold API v2 | VN gold | ✅ | Bearer token | Token expires every 15 days |
| Metals-API | Global metals | ✅ tier | API key | Free: limited calls; paid: 60s updates |
| GoldAPI.io | Global metals | ✅ | Header token | Backup for Metals-API |
| SSI FastConnect | VN stocks streaming | ✅ | Account (in-person reg.) | True WebSocket; Phase 2 |
| EODHD | Global gold history | ⚠️ | API key | 20+ year history; Phase 3 |

---

## Adding a New Data Domain

1. **Source** — add `packages/kactus-data/src/kactus_data/sources/<domain>/<provider>.py` subclassing `HttpDataSource` or `VnstockSource`
2. **Table** — add `sources/<domain>/tables.py` with `Table` + `Column` definitions
3. **Credentials** — add `<provider>_api_key: str | None = None` to `DataSettings`
4. **Export** — update `sources/<domain>/__init__.py`
5. **Service** — add `packages/kactus-fin/src/kactus_fin/<domain>/service.py` with `@staticmethod` methods calling `SyncPipeline`
6. **Schema** — add `<domain>/schema.py` inheriting `BaseSchema`
7. **API** — add `<domain>/api.py` using `KactusAPIRouter`
8. **Register** — add `<domain>/app.py` and register in `kactus_fin/app.py`
9. **Test** — add `packages/kactus-fin/tests/test_<domain>_service.py`
