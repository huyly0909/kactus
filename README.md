# Kactus

A Python monorepo managed by **uv workspaces** for gold price data processing, analytics, and API services.

## Packages

| Package | Description | Port |
|---------|-------------|------|
| [kactus-common](libs/core/kactus-common/) | Shared infrastructure: DB clients, schemas, events, logging, exceptions | — |
| [kactus-data](libs/kactus-data/) | Data processing, scraping, ETL pipelines | — |
| [kactus-fin](services/kactus-fin/) | FastAPI backend server (main API) | 17600 |
| [kactus-fin-gateway](services/kactus-fin-gateway/) | FastAPI gateway server (public APIs) | 17601 |
| [deploy](deploy/) | Docker Compose configs for dev/stag/prod | — |

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

### Run Servers (local)

```bash
python manage.py fin dev        # port 17600, hot-reload
python manage.py fin-gw dev     # port 17601, hot-reload
```

### Run Servers (Docker)

```bash
cd deploy/dev      # or stag / prod
docker compose up -d

# Run migrations
docker compose exec kactus-fin python manage.py fin db upgrade
docker compose exec kactus-fin-gw python manage.py fin-gw db upgrade
```

### Run Tests

```bash
uv run pytest                   # all tests
uv run pytest services/kactus-fin/tests/   # single package
```

## Development

```bash
# Add dependency to a package
cd libs/core/kactus-common && uv add <package>

# Sync a specific package
uv sync --package kactus-fin

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

## Architecture

```
kactus-fin  ──────┐
kactus-fin-gateway ──┤──▶ kactus-common
kactus-data  ─────┘
```

See [.cursorrules](.cursorrules) for detailed coding conventions and AI agent guidance.
