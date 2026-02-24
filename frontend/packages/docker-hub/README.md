# Docker Hub — Kactus Bloom Deployment

Docker Compose configurations for deploying the Kactus Bloom frontend across environments.

## Environments

| Environment | Directory | API Target |
|-------------|-----------|------------|
| Development | `dev/` | `localhost:17600` |
| Staging | `stag/` | `stag-api.kactus.io` |
| Production | `prod/` | `api.kactus.io` |

## Usage

```bash
# Pick environment and start
cd packages/docker-hub/dev       # or stag / prod
docker compose up -d

# Rebuild after code changes
docker compose up -d --build

# View logs
docker compose logs -f bloom-app

# Stop
docker compose down
```

## Files

- `Dockerfile.bloom-app` — Multi-stage build: pnpm install + vite build → nginx
- `nginx.conf` — SPA routing, static asset caching, security headers, gzip
- `<env>/docker-compose.yml` — Service definition per environment
- `<env>/.env` — Environment-specific variables
