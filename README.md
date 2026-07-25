# Kactus

Unified monorepo for the Kactus fintech platform (gold prices, stocks, financial
reports): a Python backend (**uv workspaces**), a React frontend (**bun +
turborepo**), and one deployment setup for the whole cluster.

```
kactus/
├── backend/      # Python uv workspace (FastAPI services + libs)
├── frontend/     # TypeScript bun/turborepo workspace (bloom-app + bloom-ui)
├── deploy/       # Dockerfiles + docker-compose per env (dev/stag/prod)
└── docs/
```

## Packages

| Package | Description | Port |
|---------|-------------|------|
| [kactus-common](backend/libs/core/kactus-common/) | Shared infrastructure: DB clients, schemas, events, logging, exceptions | — |
| [kactus-data](backend/libs/kactus-data/) | Data processing, scraping, ETL pipelines | — |
| [kactus-notification](backend/libs/kactus-notification/) | Notification domain (channels, templates, delivery) | — |
| [kactus-fin](backend/services/kactus-fin/) | FastAPI backend server — control plane | 17600 |
| [kactus-fin-gateway](backend/services/kactus-fin-gateway/) | FastAPI gateway server (public APIs) | 17601 |
| [kactus-data-server](backend/services/kactus-data-server/) | ETL + DuckDB + crawl scheduler — data plane | 17602 |
| [bloom-app](frontend/packages/bloom-app/) | React SPA (Vite, shadcn/ui, TanStack Query) | 17630 |
| [bloom-ui](frontend/packages/bloom-ui/) | Shared component library (`@kactus-bloom/ui`) | — |
| [deploy](deploy/) | Dockerfiles + Docker Compose configs for dev/stag/prod | — |

## Quick Start

### Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh/) 1.x (frontend)

### Backend

```bash
git clone <repo-url> kactus && cd kactus/backend
uv sync --all-packages

python manage.py fin dev            # port 17600, hot-reload
python manage.py fin-gw dev         # port 17601, hot-reload
python manage.py data-server dev    # port 17602 (data plane)
```

### Frontend

```bash
cd frontend
bun install
bun run dev                         # vite on :17630, proxies /api → :17600
```

### Docker (whole cluster, frontend included)

```bash
cd deploy/dev      # or stag / prod
docker compose up -d

# Run migrations
docker compose exec kactus-fin python manage.py fin db upgrade
```

The `bloom-app` container serves the SPA and reverse-proxies `/api` to
`kactus-fin` — one origin, no CORS.

### Tests

```bash
cd backend
uv run pytest                              # all backend tests
uv run pytest services/kactus-fin/tests/   # single package
uv run lint-imports                        # layer contract

cd ../frontend
bun run test                               # vitest
bun run lint
```

## Development

```bash
# Add dependency to a backend package
cd backend/libs/core/kactus-common && uv add <package>

# Pre-commit hooks (repo root — covers backend and frontend)
pre-commit install
pre-commit run --all-files
```

## Architecture

```
backend/services/kactus-fin ────────┐
backend/services/kactus-fin-gateway ─┤──▶ backend/libs/core/kactus-common
backend/services/kactus-data-server ─┤
backend/libs/kactus-data ───────────┤
backend/libs/kactus-notification ───┘

frontend/packages/bloom-app ──HTTP /api──▶ kactus-fin (17600)
```

See [CLAUDE.md](CLAUDE.md) for detailed architecture and conventions, and
[docs/](docs/) for feature deep-dives.
