---
name: project-conventions
description: Core architecture, TypeScript conventions, and guardrails for the kactus-bloom monorepo. Use on every task involving code changes in the bloom project.
---

# Kactus Bloom — Project Conventions

> **Other skills**: See `component-development.md`, `data-fetching.md`, `routing-and-layouts.md`, `testing.md` for detailed workflows.

## Architecture

Kactus Bloom is a **pnpm workspaces + Turborepo** monorepo with 3 packages:

| Package | Import As | Purpose |
|---------|-----------|---------|
| `bloom-ui` | `@kactus-bloom/ui` | Shared UI components, hooks, stores, services, types, theme |
| `bloom-app` | — | Main web application (pages, routes, layouts) |
| `docker-hub` | — | Docker Compose configs for dev/stag/prod deployment |

### Dependency Flow (One-Way)

```
bloom-app ──▶ bloom-ui
```

**Never import from bloom-app into bloom-ui.** `docker-hub` is infrastructure-only.

## Directory Structure

```
kactus-bloom/
├── packages/
│   ├── bloom-ui/src/
│   │   ├── components/         # Shared UI (folder per component)
│   │   │   ├── AppLayout/      # AppLayout.tsx + index.ts
│   │   │   ├── ChartCard/
│   │   │   ├── ChatBox/
│   │   │   └── DataTable/
│   │   ├── hooks/              # useAuth, useApiQuery, useApiMutation, useProject, usePermission, useWebSocket, useNotification
│   │   ├── stores/             # authStore, projectStore, permissionStore, uiStore
│   │   ├── services/           # apiClient, authService, projectService, adminService
│   │   ├── types/              # api.ts, auth.ts, project.ts
│   │   ├── utils/
│   │   ├── theme/              # Mantine theme customization
│   │   └── index.ts            # Barrel: components + theme only
│   ├── bloom-app/src/
│   │   ├── pages/              # Folder per page (Login/, Dashboard/, Admin/, etc.)
│   │   ├── router/             # index.tsx + guards (AuthGuard, AdminGuard, ProjectGuard)
│   │   ├── layouts/            # AuthLayout, MainLayout
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── docker-hub/
├── package.json                # Root with Turborepo scripts
├── pnpm-workspace.yaml
├── turbo.json
├── tsconfig.base.json
└── eslint.config.js
```

## Tech Stack

- **React 18** + **TypeScript 5** — UI framework
- **Vite 6** — Build + dev server (HMR)
- **Mantine 7** — UI component library
- **Recharts** — Charts | **Lucide React** — Icons
- **React Router v7** — Routing (with `Outlet` layout pattern)
- **TanStack Query v5** — Server state (via `useApiQuery` / `useApiMutation` wrappers)
- **Zustand** — Client state (auth, project, permissions, UI)
- **Axios** — HTTP client (`withCredentials: true`, 401 interceptor)
- **React Hook Form + Zod** — Forms + schema validation
- **js-cookie** — Project selection cookie
- **Native WebSocket** — Real-time communication
- **ESLint 9 + Prettier** — Code quality (Husky + lint-staged)
- **Vitest + React Testing Library** — Testing

## Backend API

Backend: `kactus-fin` (FastAPI) at port **17600**. Gateway: port **17601**.

Response envelope:
```json
{ "data": { ... }, "message": "Success", "code": 200 }
```

TypeScript type: `ApiResponse<T>` from `bloom-ui/src/types/api.ts`.

## TypeScript Conventions

- Always `.ts` / `.tsx` — never `.js` / `.jsx`
- Use `interface` for object shapes, `type` for unions/intersections
- Use `import type` for type-only imports
- Never use `any` — use `unknown` or define proper types

## File Naming

| Type | Convention | Example |
|------|-----------|---------|
| Components | `PascalCase.tsx` in folder | `DataTable/DataTable.tsx` + `index.ts` |
| Hooks | `use` prefix, `camelCase.ts` | `useAuth.ts` |
| Stores | `Store` suffix, `camelCase.ts` | `authStore.ts` |
| Services | `Service` suffix, `camelCase.ts` | `authService.ts` |
| Utils/Types | `camelCase.ts` | `formatters.ts` |
| Pages | Folder with `index.tsx` | `Dashboard/index.tsx` |

## Import Paths

bloom-ui uses **sub-path exports** — import from specific sub-paths, not the barrel:

```tsx
// ✅ Components and theme — from barrel
import { DataTable, ChartCard, AppLayout } from '@kactus-bloom/ui';

// ✅ Hooks — sub-path
import { useAuth, useApiQuery, useApiMutation } from '@kactus-bloom/ui/hooks';
import { useProject, usePermission } from '@kactus-bloom/ui/hooks';

// ✅ Stores — sub-path
import { useAuthStore, useProjectStore, usePermissionStore } from '@kactus-bloom/ui/stores';

// ✅ Services — sub-path
import { authService, projectService, apiClient } from '@kactus-bloom/ui/services';

// ✅ Types — sub-path
import type { ApiResponse, User, Project } from '@kactus-bloom/ui/types';

// ✅ Mantine
import { Button, Modal, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';

// ✅ Other libraries
import { LineChart, Line, XAxis, YAxis } from 'recharts';
import { Search, Bell, Settings } from 'lucide-react';

// ❌ Never cross package boundaries with relative imports
import { DataTable } from '../../bloom-ui/src/components/DataTable';
```

## Where to Put Code

| You need to... | Put it in... |
|----------------|-------------|
| Add a reusable component | `bloom-ui/src/components/<Name>/` (folder with `<Name>.tsx` + `index.ts`) |
| Add a shared hook | `bloom-ui/src/hooks/` → export from `hooks/index.ts` |
| Add a Zustand store | `bloom-ui/src/stores/` → export from `stores/index.ts` |
| Add an API service | `bloom-ui/src/services/` → export from `services/index.ts` |
| Add shared types | `bloom-ui/src/types/` → export from `types/index.ts` |
| Add utilities | `bloom-ui/src/utils/` |
| Add a page/route | `bloom-app/src/pages/<PageName>/` + register in `router/index.tsx` |
| Customize Mantine theme | `bloom-ui/src/theme/` |
| Add/modify Docker config | `docker-hub/` |

## Environment Variables

Prefix with `VITE_`:
```env
VITE_API_BASE_URL=http://localhost:17600/api
VITE_WS_BASE_URL=ws://localhost:17600/ws
VITE_APP_NAME=Kactus Bloom
```

## Quick Commands

```bash
pnpm dev              # Start all packages in dev mode
pnpm build            # Production build
pnpm lint             # Run ESLint
pnpm test             # Run all tests
pnpm format           # Run Prettier
```

## Docker Deployment

```bash
cd packages/docker-hub/dev       # or stag / prod
docker compose up -d
docker compose up -d --build     # rebuild after code changes
```

## Don't Do This

- ❌ Use `.js` / `.jsx` — always `.ts` / `.tsx`
- ❌ Use `any` — define proper types
- ❌ Use class components — always functional + hooks
- ❌ Use `default export` for components — use named exports
- ❌ Import bloom-app → bloom-ui (one-way dependency only)
- ❌ Store tokens in localStorage — session is in httpOnly cookie
- ❌ Make API calls directly in components — use services + `useApiQuery`/`useApiMutation`
- ❌ Install Ant Design, MUI, or Chakra — use Mantine only
- ❌ Use `var` — use `const` / `let`
- ❌ Skip TypeScript interfaces for props
- ❌ Use `useEffect` for data fetching — use `useApiQuery` or TanStack Query
- ❌ Put Dockerfiles in app packages — keep them in `docker-hub/`
- ❌ Skip tests — every feature needs tests, run `pnpm test` before committing
- ❌ Import hooks/stores/services from barrel `@kactus-bloom/ui` — use sub-paths (`/hooks`, `/stores`, `/services`)
