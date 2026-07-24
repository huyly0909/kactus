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
| `kactus-fin` | Built from `Dockerfile.fin` | 17600 | Main API server |
| `kactus-fin-gw` | Built from `Dockerfile.fin-gw` | 17601 | Gateway API server |

## Environment Comparison

| | `dev` | `stag` | `prod` |
|---|---|---|---|
| `kactus-fin` workers | 1 (reload) | 1 | 1 |
| `kactus-fin-gw` workers | 1 (reload) | 2 | 4 |
| Log level | debug | info | warning |
| Restart | no | unless-stopped | always |
| Source volumes | ✅ (hot-reload) | ❌ | ❌ |

### Why `kactus-fin` is pinned to one worker

It runs the portfolio APScheduler in-process. N workers would be N schedulers:
N duplicate crawls per tick, N× the vnstock rate limit burned, and DuckDB
`IOException: Could not set lock on file` when they collide on a write. The
scheduler has to move into its own single-replica service before this can be
raised.

The other two reasons are already gone. With `KACTUS_COORDINATION_BACKEND=redis`
(set in every compose file) the SSE broker publishes through Redis so a client
hears events from any worker, and the Zalo QR session store lives in Redis so
the 5 login steps may land on different workers.

`kactus-fin-gw` is stateless and keeps its worker count.

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

# kactus-fin-gateway
KACTUS_GW_DATABASE_URL=postgresql+asyncpg://kactus:<password>@postgres:5432/kactus
KACTUS_GW_DEBUG=false
```

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

### 6. Verify deployment

```bash
# Health checks
curl http://localhost:17600/health    # kactus-fin
curl http://localhost:17601/health    # kactus-fin-gateway
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
