# Docker Hub — Deployment Guide

Manual deployment guide for Kactus services using Docker Compose.

## Prerequisites

- Docker Engine 24+
- Docker Compose v2+
- Git access to the repository

## Services

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| `postgres` | `postgres:16-alpine` | 5432 | PostgreSQL database |
| `redis` | `redis:7-alpine` | 6379 | Redis cache |
| `kactus-fin` | Built from `Dockerfile.fin` | 17600 | Main API server (control plane) |
| `kactus-fin-gw` | Built from `Dockerfile.fin-gw` | 17601 | Gateway API server |
| `kactus-data-server` | Built from `Dockerfile.data-server` | 17602 | ETL + DuckDB + crawl scheduler (data plane) |

## Environment Comparison

| | `dev` | `stag` | `prod` |
|---|---|---|---|
| `kactus-fin` workers | 1 (reload) | 2 | 4 |
| `kactus-fin-gw` workers | 1 (reload) | 2 | 4 |
| `kactus-data-server` workers | **1** (reload) | **1** | **1** |
| `kactus-data-server` port published | ✅ 17602 | ❌ | ❌ |
| Log level | debug | info | warning |
| Restart | no | unless-stopped | always |
| Source volumes | ✅ (hot-reload) | ❌ | ❌ |

### Why `kactus-data-server` is pinned to one worker and one replica

It holds the only read-write DuckDB handle in the deployment and runs the crawl
APScheduler in-process. A second process of either kind means
`IOException: Could not set lock on file` on every write and N× the vnstock rate
limit burned per tick, with no leader election to fall back on. Scaling the crawl
out is a Redis-queue project, not a `--workers` change.

The service warns loudly at boot if it detects more than one worker
(`WEB_CONCURRENCY` or `--workers N`), and again if
`KACTUS_COORDINATION_BACKEND` is not `redis` — on `memory` its crawl
completions go to its own in-process broker and no browser ever sees them.

### Why `kactus-fin` is no longer pinned to one worker

All three reasons are gone. `KACTUS_COORDINATION_BACKEND=redis` (set in every
compose file) shares the SSE broker and the Zalo QR session store across
processes, and the scheduler plus the DuckDB handle now live in
`kactus-data-server`. The control plane holds no OLAP state and reads market
data over HTTP.

## Deploy Steps

### 1. Clone the repository

```bash
ssh user@your-server
git clone <repo-url> /opt/kactus
cd /opt/kactus
```

### 2. Choose environment

```bash
# Development
cd deploy/dev

# Staging
cd deploy/stag

# Production
cd deploy/prod
```

### 3. Configure environment variables

Edit the `.env` file in your chosen environment:

```bash
cp .env .env.bak   # backup defaults
vi .env             # edit passwords, URLs, etc.
```

> ⚠️ **Production**: Change `POSTGRES_PASSWORD` and all `DATABASE_URL` passwords before deploying!

Key variables:

```bash
# Postgres
POSTGRES_USER=kactus
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=kactus

# kactus-fin
KACTUS_DATABASE_URL=postgresql+asyncpg://kactus:<password>@postgres:5432/kactus
KACTUS_DEBUG=false

# Required once KACTUS_COORDINATION_BACKEND=redis: Zalo QR sessions carry
# credentials and are Fernet-encrypted before they are written to Redis.
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
KACTUS_ENCRYPTION_KEY=<fernet-key>

# Shared secret between kactus-fin and kactus-data-server. Every /internal
# route on the data plane requires it in an X-Service-Token header, and an
# unset value fails every request rather than waving them through.
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
KACTUS_INTERNAL_SERVICE_TOKEN=<random-token>

# kactus-fin-gateway
KACTUS_GW_DATABASE_URL=postgresql+asyncpg://kactus:<password>@postgres:5432/kactus
KACTUS_GW_DEBUG=false
```

`KACTUS_DATA_PLANE_URL` and `KACTUS_DB_PATH` are set by the compose files and
the data-plane image respectively — they should not be put in `.env`, where they
could drift out of sync with the service name and the volume mount.

### 4. Build and start services

```bash
# Build images and start all services
docker compose up -d --build

# Check status
docker compose ps

# View logs
docker compose logs -f
docker compose logs -f kactus-fin       # single service
```

### 5. Run database migrations

```bash
# kactus-fin migrations
docker compose exec kactus-fin python manage.py fin db upgrade

# kactus-fin-gateway migrations
docker compose exec kactus-fin-gw python manage.py fin-gw db upgrade
```

`kactus-data-server` ships no Alembic config on purpose: it declares no ORM
models of its own and shares kactus-fin's migration head on the same Postgres.
Two services migrating one database is how you get two heads.

### 6. Verify deployment

```bash
# Health checks
curl http://localhost:17600/health    # kactus-fin
curl http://localhost:17601/health    # kactus-fin-gateway

# The data plane is only published in dev; elsewhere, from inside the network:
docker compose exec kactus-fin curl -s http://kactus-data-server:17602/health
```

The data plane reports the three things that make it useful, and answers
`degraded` rather than failing when one is missing:

```json
{"status": "ok", "duckdb": "ok", "scheduler": "running", "redis": "ok"}
```

Its `/internal` routes are the only way to reach market data, and they require
the service token:

```bash
# 403 — no token
docker compose exec kactus-fin curl -s http://kactus-data-server:17602/internal/market/gold
# 200
docker compose exec kactus-fin curl -s \
  -H "X-Service-Token: $KACTUS_INTERNAL_SERVICE_TOKEN" \
  http://kactus-data-server:17602/internal/market/gold
```

`kactus-fin` reports Redis whenever it depends on it:

```json
{"status": "ok", "redis": "ok"}
{"status": "degraded", "redis": "unreachable"}   // SSE + Zalo QR are down
```

`redis` is absent from the response on the `memory` backend — there, an
unreachable Redis is genuinely not a fault.

## Common Operations

### Update to latest code

```bash
cd /opt/kactus
git pull origin main

cd deploy/<env>
docker compose up -d --build
```

### Create a new migration

```bash
docker compose exec kactus-fin python manage.py fin db migrate -m "add users table"
docker compose exec kactus-fin python manage.py fin db upgrade
```

### View migration history

```bash
docker compose exec kactus-fin python manage.py fin db history
docker compose exec kactus-fin python manage.py fin db current
```

### Rollback a migration

```bash
docker compose exec kactus-fin python manage.py fin db downgrade <revision>
```

### Restart a single service

```bash
docker compose restart kactus-fin
```

### Stop all services

```bash
docker compose down           # stop containers
docker compose down -v        # stop and remove volumes (⚠️ deletes data)
```

### View container resource usage

```bash
docker compose stats
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker compose logs kactus-fin

# Check if postgres is healthy
docker compose exec postgres pg_isready -U kactus

# Check if redis is healthy
docker compose exec redis redis-cli ping
```

### Database connection refused

- Ensure `postgres` service is healthy before app containers start (handled by `depends_on` + healthcheck)
- Verify `DATABASE_URL` in `.env` uses `postgres` as hostname (Docker DNS), not `localhost`

### Permission denied on volumes (dev)

```bash
# Fix ownership if bind-mounted source has wrong permissions
sudo chown -R $(id -u):$(id -g) services/ libs/
```
