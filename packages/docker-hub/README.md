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
| Workers | 1 (reload) | 2 | 4 |
| Log level | debug | info | warning |
| Restart | no | unless-stopped | always |
| Source volumes | ✅ (hot-reload) | ❌ | ❌ |

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
cd packages/docker-hub/dev

# Staging
cd packages/docker-hub/stag

# Production
cd packages/docker-hub/prod
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

## Common Operations

### Update to latest code

```bash
cd /opt/kactus
git pull origin main

cd packages/docker-hub/<env>
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
sudo chown -R $(id -u):$(id -g) packages/
```
