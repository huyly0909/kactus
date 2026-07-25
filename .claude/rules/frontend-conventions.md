---
description: Frontend coding conventions (bloom-app + bloom-ui)
globs: ["frontend/packages/bloom-app/**/*.ts", "frontend/packages/bloom-app/**/*.tsx", "frontend/packages/bloom-ui/**/*.ts", "frontend/packages/bloom-ui/**/*.tsx"]
---

# Frontend Conventions

> The frontend lives in **`frontend/`** (bun + turborepo workspace in this monorepo).

## Tech Stack
- React 18 + TypeScript 5 + Vite 6
- **Tailwind CSS v4** + **shadcn/ui** (Radix primitives + CVA) + Lucide React (icons)
- **sonner** (toasts) + Recharts (charts)
- Zustand 5 (client state) + TanStack Query v5 (server state)
- React Hook Form + Zod (forms/validation)
- React Router v7 + Axios (HTTP) + i18next (vi + en)

## Monorepo (Turborepo)
- `frontend/packages/bloom-app/` — the shipped web app (all active development)
- `frontend/packages/bloom-ui/` — shared component library (`@kactus-bloom/ui`)
- `bloom-app` MAY import from `bloom-ui`, NEVER the reverse. (Today `bloom-app`
  owns its own copy of the shadcn primitives and does not yet consume `bloom-ui`.)

## Import Rules
```typescript
// shadcn primitives — lowercase files under @/components/ui
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { cn } from '@/lib/utils';

// Feature code by alias — @ = src, @modules = src/modules
import { usePortfolios } from '@/hooks/usePortfolioQuery';
import { portfolioService } from '@/services/portfolioService';
import { useAuthStore } from '@/store/authStore';
import type { NotificationChannel } from '@/types/notification';
import { PortfolioListPage } from '@modules/portfolio/pages/PortfolioListPage';

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
import { type FC } from 'react';
import { cn } from '@/lib/utils';

interface MyComponentProps {
  title: string;
  onAction: () => void;
}

export const MyComponent: FC<MyComponentProps> = ({ title, onAction }) => {
  return <div className={cn('flex items-center gap-2')}>{title}</div>;
};
```
- Named exports only (NO default exports)
- Functional components with `FC<Props>`
- shadcn/ui (Radix + Tailwind) for UI, Lucide for icons — no other UI/icon libraries
- Style with Tailwind classes via `cn()`; variants with `class-variance-authority`
- User-facing strings go through i18next (`useTranslation()` → `t('key')`)

## Data Fetching
- Use TanStack Query hooks (`useQuery` / `useMutation`, e.g. `usePortfolios()`) — NOT `useEffect` for API calls
- Use a `*Service` from `@/services` for the actual axios calls
- Toasts via **sonner** (`import { toast } from 'sonner'`), not a UI-kit notification API

## State Management
- Zustand stores for client state (auth, UI, filters)
- TanStack Query for server state (API data) — with a query-key factory per feature
- Services for API calls (never call axios directly in components)

## File Naming
| Type | Convention | Example |
|------|-----------|---------|
| shadcn primitives | lowercase (kebab) | `button.tsx`, `data-table.tsx` |
| Module components | PascalCase | `QuotesTable.tsx`, `ChannelFormDialog.tsx` |
| Pages | PascalCase under `modules/<name>/pages/` | `PortfolioListPage.tsx` |
| Hooks | camelCase with `use` prefix | `usePortfolioQuery.ts` |
| Stores | camelCase with `Store` suffix | `authStore.ts` |
| Services | camelCase with `Service` suffix | `portfolioService.ts` |

## Don't Do This
- Import inside functions
- Use `default export`
- Use `any` type
- Use Mantine / Ant Design / MUI / Chakra — use shadcn/ui (Radix + Tailwind) only
- Call APIs directly in components (use services)
- Use `useEffect` for data fetching (use TanStack Query)
- Store API data in Zustand (use TanStack Query cache)
- Hardcode user-facing strings (use i18next)
