---
description: Frontend coding conventions for usonia-app and usonia-ui
globs: ["frontend/**/*.ts", "frontend/**/*.tsx"]
---

# Frontend Conventions

## Tech Stack
- React 18 + TypeScript 5 + Vite 6
- Mantine 7 (UI) + Lucide React (icons) + Recharts (charts)
- Zustand 5 (client state) + TanStack Query v5 (server state)
- React Router v7 + Axios (HTTP)

## Monorepo
- `frontend/packages/usonia-app/` — Main web app
- `frontend/packages/usonia-ui/` — Shared UI library (`@usonia/ui`)
- usonia-app imports from usonia-ui, NEVER the reverse

## Import Rules
```typescript
// Components from barrel
import { DataTable, ChartCard, StatCard } from '@usonia/ui';

// Sub-paths for hooks/stores/services
import { useApiQuery } from '@usonia/ui/hooks';
import { useConfigStore } from '@usonia/ui/stores';
import { dashboardService } from '@usonia/ui/services';
import type { WorkerList } from '@usonia/ui/types';
import { formatDuration } from '@usonia/ui/utils';

// NEVER import hooks/stores/services from barrel
// NEVER use cross-package relative imports
```

## TypeScript
- Always `.ts` / `.tsx` (never `.js` / `.jsx`)
- `interface` for object shapes, `type` for unions
- `import type` for type-only imports
- NO `any` — use `unknown` or proper types
- Strict mode enabled

## Component Pattern
```typescript
interface MyComponentProps {
  title: string;
  onAction: () => void;
}

export const MyComponent: FC<MyComponentProps> = ({ title, onAction }) => {
  return <div>{title}</div>;
};
```
- Named exports only (NO default exports)
- Functional components with `FC<Props>`
- Mantine for UI, Lucide for icons — no other UI/icon libraries

## Data Fetching
- Use `useApiQuery<T>()` from `@usonia/ui/hooks` — NOT `useEffect` for API calls
- Use `dashboardService` from `@usonia/ui/services` for API methods
- Use `refetchInterval` for auto-refresh on monitoring data

## State Management
- Zustand stores for client state (UI, config, filters)
- TanStack Query for server state (API data)
- Services for API calls (never call axios directly in components)

## File Naming
| Type | Convention | Example |
|------|-----------|---------|
| Components | PascalCase folder + file | `StatCard/StatCard.tsx` + `index.ts` |
| Hooks | camelCase with `use` prefix | `useApi.ts` |
| Stores | camelCase with `Store` suffix | `configStore.ts` |
| Services | camelCase with `Service` suffix | `dashboardService.ts` |
| Pages | PascalCase folder + `index.tsx` | `Monitor/index.tsx` |

## Don't Do This
- Import inside functions
- Use `default export`
- Use `any` type
- Use CSS modules / Tailwind / styled-components (Mantine only)
- Call APIs directly in components (use services)
- Use `useEffect` for data fetching (use TanStack Query)
- Store API data in Zustand (use TanStack Query cache)
