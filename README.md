# Kactus

A Python monorepo managed by **uv workspaces** for gold price data processing, analytics, and API services.

## Packages

| Package | Description | Port |
|---------|-------------|------|
| [kactus-common](packages/kactus-common/) | Shared infrastructure: DB clients, schemas, events, logging, exceptions | — |
| [kactus-data](packages/kactus-data/) | Data processing, scraping, ETL pipelines | — |
| [kactus-fin](packages/kactus-fin/) | FastAPI backend server (main API) | 8000 |
| [kactus-fin-gateway](packages/kactus-fin-gateway/) | FastAPI gateway server (public APIs) | 8001 |

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Install

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install all packages
git clone <repo-url> kactus && cd kactus
uv sync --all-packages
```

### Run Servers

```bash
# Start kactus-fin (port 8000)
uv run uvicorn kactus_fin.app:app --host 0.0.0.0 --port 8000 --reload

# Start kactus-fin-gateway (port 8001)
uv run uvicorn kactus_fin_gateway.app:app --host 0.0.0.0 --port 8001 --reload
```

### Run Tests

```bash
# All tests
uv run pytest

# Single package
uv run pytest packages/kactus-common/tests/
uv run pytest packages/kactus-fin/tests/
```

## Development

```bash
# Add dependency to a package
cd packages/kactus-common && uv add <package>

# Sync all packages after changes
uv sync --all-packages
```

## Architecture

```
kactus-fin  ──────┐
kactus-fin-gateway ──┤──▶ kactus-common
kactus-data  ─────┘
```

See [.cursorrules](.cursorrules) for detailed coding conventions and AI agent guidance.
