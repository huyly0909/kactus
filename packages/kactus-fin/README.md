# kactus-fin

FastAPI backend server for the Kactus monorepo — serves financial data via a REST API.

## Installation

Automatically installed as a workspace dependency:

```bash
# From the monorepo root
uv sync --all-packages
```

## Quick Start

```bash
# Development server (hot reload)
uv run uvicorn kactus_fin.app:app --reload --port 8000

# Health check
curl http://localhost:8000/health
# → {"status": "ok"}

# Interactive API docs
open http://localhost:8000/docs
```

## Configuration

Settings are loaded from environment variables (prefixed `KACTUS_`) or a `.env` file:

```bash
# .env
KACTUS_DEBUG=true
KACTUS_HOST=0.0.0.0
KACTUS_PORT=8000
KACTUS_DB_PATH=kactus.duckdb
```

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `KACTUS_APP_NAME` | `str` | `Kactus Fin` | Application name |
| `KACTUS_APP_VERSION` | `str` | `0.1.0` | Application version |
| `KACTUS_DEBUG` | `bool` | `false` | Enable debug mode |
| `KACTUS_HOST` | `str` | `0.0.0.0` | Server bind address |
| `KACTUS_PORT` | `int` | `8000` | Server bind port |
| `KACTUS_DB_PATH` | `str` | `kactus.duckdb` | DuckDB database path |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI (auto-generated) |
| `GET` | `/redoc` | ReDoc (auto-generated) |

## Package Structure

```
kactus_fin/
├── app.py          # FastAPI app factory + lifespan
├── config.py       # Pydantic Settings (env-based config)
└── api/
    └── health.py   # Health check endpoint
```

## Adding New Endpoints

1. Create a new router file in `api/`:

```python
# packages/kactus-fin/src/kactus_fin/api/prices.py
from fastapi import APIRouter
from kactus_common import DatabaseClient

router = APIRouter(prefix="/prices", tags=["prices"])

@router.get("/")
async def list_prices():
    db = DatabaseClient("kactus.duckdb")
    result = db.execute("SELECT * FROM gold_prices ORDER BY date DESC LIMIT 30")
    return {"prices": result.fetchall()}
```

2. Register the router in `app.py`:

```python
from kactus_fin.api.prices import router as prices_router

# Inside create_app()
app.include_router(prices_router)
```

## Testing

```bash
uv run pytest packages/kactus-fin/tests/ -v
```
