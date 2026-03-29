# Kactus

A Python monorepo managed by **uv workspaces**. Provides a FastAPI backend for Vietnamese financial data — stock prices (HOSE/HNX/UPCOM), domestic gold prices (SJC, DOJI, PNJ), and global precious metal prices (XAU/USD).

## Packages

| Package | Import As | Purpose | Port |
|---------|-----------|---------|------|
| [kactus-common](packages/kactus-common/) | `kactus_common` | Shared infrastructure: DB clients, schemas, router, exceptions, auth | — |
| [kactus-data](packages/kactus-data/) | `kactus_data` | Data sources, ETL pipelines, DuckDB storage | — |
| [kactus-fin](packages/kactus-fin/) | `kactus_fin` | FastAPI main API server | 17600 |
| [kactus-fin-gateway](packages/kactus-fin-gateway/) | `kactus_fin_gateway` | FastAPI public gateway | 17601 |
| [docker-hub](packages/docker-hub/) | — | Docker Compose configs (dev/stag/prod) | — |

## API Features

| Domain | Endpoints | Data Source |
|--------|-----------|-------------|
| Stocks | `GET /api/stock`, `GET /api/stock/{symbol}/ohlcv`, `POST /api/stock/sync-*` | Vnstock (TCBS/SSI/KBS) |
| Company | `GET /api/company`, `GET /api/company/{symbol}`, `POST /api/company/sync` | Vnstock |
| Finance | `GET /api/finance`, `GET /api/finance/{symbol}`, `POST /api/finance/sync` | Vnstock |
| VN Gold | `GET /api/gold/vn`, `POST /api/gold/vn/sync` | VNAppMob Gold API v2 |
| Global Gold | `GET /api/gold/global`, `POST /api/gold/global/sync` | Metals-API |

All responses use the envelope: `{ "data": T, "message": "string", "code": "string" }`.

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Install

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone <repo-url> kactus && cd kactus
uv sync --all-packages
```

### Configure

Copy `.env.example` to `.env` and fill in:

```bash
# Required for gold data
KACTUS_VNAPPMOB_TOKEN=your_vnappmob_bearer_token   # expires every 15 days
KACTUS_METALS_API_KEY=your_metals_api_key

# Database
KACTUS_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/kactus
KACTUS_DB_PATH=kactus.duckdb

# CORS (comma-separated origins)
KACTUS_CORS_ALLOWED_ORIGINS=http://localhost:17630
```

### Run (local)

```bash
python manage.py fin dev        # port 17600, hot-reload
python manage.py fin-gw dev     # port 17601, hot-reload
```

### Run (Docker)

```bash
cd packages/docker-hub/dev
docker compose up -d

# Apply migrations
docker compose exec kactus-fin python manage.py fin db upgrade
```

### Tests

```bash
uv run pytest                                  # all tests (333+)
uv run pytest packages/kactus-fin/tests/       # single package
uv run pytest -k "test_gold"                   # filter by name
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for a full breakdown.

```
kactus-bloom (React :17630)
        │ HTTP
        ▼
kactus-fin (FastAPI :17600)
        │
        ├─ stock / company / finance  ──▶  Vnstock (Python lib)
        ├─ gold/vn                    ──▶  VNAppMob API v2
        └─ gold/global                ──▶  Metals-API
                │
                ▼
          DuckDB (OLAP cache)
          PostgreSQL (OLTP — users, projects)
```

## Development

```bash
# Add dependency to a package
cd packages/kactus-common && uv add <package>

# Sync all packages
uv sync --all-packages

# Database migrations
python manage.py fin db migrate -m "describe change"
python manage.py fin db upgrade

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

## Coding Guidelines

See [CLAUDE.md](CLAUDE.md) for full conventions enforced in this repo.
