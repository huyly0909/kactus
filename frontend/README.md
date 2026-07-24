# Kactus Bloom

Fintech frontend monorepo built with React + TypeScript + shadcn/ui + Tailwind CSS v4.

## Quick Start

```bash
# Install dependencies
pnpm install

# Start dev server (port 17630)
pnpm dev --filter bloom-app

# Build for production
pnpm build --filter bloom-app
```

## Test

```bash
# Run all tests
pnpm test

# Run tests for a specific package
pnpm test --filter bloom-app
```

## Packages

| Package | Purpose |
|---------|---------|
| `bloom-ui` | Shared UI components, hooks, stores, services |
| `bloom-app` | Main web application |
| `docker-hub` | Docker Compose configs (dev/stag/prod) |

## Docker Deployment

```bash
cd packages/docker-hub/dev   # or stag / prod
docker compose up -d
```

## Tech Stack

React 18 · TypeScript · Vite 6 · Tailwind CSS v4 · shadcn/ui (Radix primitives + CVA) · sonner (toasts) · Recharts · TanStack Query · Zustand · React Hook Form + Zod · Axios · React Router v7

See [.cursorrules](.cursorrules) for full conventions.
