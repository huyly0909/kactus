---
name: data-fetching
description: Use when adding API calls, TanStack Query hooks, Zustand stores, or working with the auth flow. Covers services, useApiQuery/useApiMutation, stores, and state management.
---

# Data Fetching & State Management Skill

## API Services — Object-Style Pattern

Services are defined as **object literals** in `bloom-ui/src/services/`. Each method unwraps `data.data` from the `ApiResponse<T>` envelope:

```tsx
// bloom-ui/src/services/transactionService.ts
import { apiClient } from './apiClient';
import type { ApiResponse } from '../types';

interface Transaction { id: string; amount: number; status: string; }
interface TransactionCreatePayload { amount: number; description: string; }

export const transactionService = {
  /** List transactions. */
  getAll: async (params?: Record<string, string>) => {
    const { data } = await apiClient.get<ApiResponse<Transaction[]>>('/api/transactions', { params });
    return data.data;
  },

  /** Create a transaction. */
  create: async (payload: TransactionCreatePayload) => {
    const { data } = await apiClient.post<ApiResponse<Transaction>>('/api/transactions', payload);
    return data.data;
  },
};
```

After creating, export from `services/index.ts`:
```tsx
export { transactionService } from './transactionService';
```

**Rules:**
- Services use **object-style** — `transactionService.getAll()`, not standalone functions
- Always unwrap `data.data` in the service (callers get the inner payload directly)
- Use the shared `apiClient` (Axios with `withCredentials: true` + 401 interceptor)
- Type responses with `ApiResponse<T>` from `bloom-ui/src/types`

## apiClient

Shared Axios instance in `bloom-ui/src/services/apiClient.ts`:
- Base URL from `import.meta.env.VITE_API_BASE_URL`
- `withCredentials: true` — sends httpOnly cookies automatically
- 401 interceptor → redirects to `/login` (avoids redirect loop)
- 30s timeout

## useApiQuery — GET Requests

Use the `useApiQuery` wrapper hook (not raw `useQuery`):

```tsx
import { useApiQuery } from '@kactus-bloom/ui/hooks';

// In component:
const { data, isLoading, error } = useApiQuery<Transaction[]>(
  ['transactions', projectId],   // queryKey
  '/api/transactions',           // url
  { params: { project_id: projectId } },  // axios config (optional)
);

// data is ApiResponse<T> — access data.data for the payload
const transactions = data?.data ?? [];
```

## useApiMutation — POST/PUT/PATCH/DELETE

Use the `useApiMutation` wrapper hook (not raw `useMutation`):

```tsx
import { useApiMutation } from '@kactus-bloom/ui/hooks';
import { notifications } from '@mantine/notifications';

const mutation = useApiMutation<Transaction, TransactionCreatePayload>(
  '/api/transactions',    // url
  'post',                 // method: 'post' | 'put' | 'patch' | 'delete'
  {
    onSuccess: () => {
      notifications.show({ title: 'Success', message: 'Transaction created', color: 'green' });
    },
    onError: (error) => {
      notifications.show({ title: 'Error', message: error.message, color: 'red' });
    },
  },
);

// Usage
mutation.mutate({ amount: 100, description: 'Test' });
```

`useApiMutation` automatically invalidates **all queries** on `onSettled`.

## Zustand Stores

Client-only state in `bloom-ui/src/stores/`. Existing stores:

| Store | State | Purpose |
|-------|-------|---------|
| `useAuthStore` | `user`, `isAuthenticated`, `isLoading` | Auth state (session cookie-based) |
| `useProjectStore` | `currentProject`, `isLoading` | Selected project + cookie persistence via `js-cookie` |
| `usePermissionStore` | `permissions`, `role`, `isSuperuser` | User permissions for current project |
| `useUIStore` | UI preferences | Sidebar state, etc. |

### Store Pattern (actual code)

```tsx
import { create } from 'zustand';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,  // true until /me check completes

  setUser: (user) => set({ user, isAuthenticated: user !== null, isLoading: false }),
  setLoading: (isLoading) => set({ isLoading }),
  clearAuth: () => set({ user: null, isAuthenticated: false, isLoading: false }),
}));
```

### Project Store — Cookie Persistence

```tsx
import Cookies from 'js-cookie';

const PROJECT_COOKIE_NAME = 'kactus_project_id';

// setProject → Cookies.set(PROJECT_COOKIE_NAME, project.id, { expires: 365 })
// clearProject → Cookies.remove(PROJECT_COOKIE_NAME)
// getProjectIdFromCookie → Cookies.get(PROJECT_COOKIE_NAME)
```

## Convenience Hooks

Hooks in `bloom-ui/src/hooks/` wrap store + service for convenience:

| Hook | Wraps | Methods |
|------|-------|---------|
| `useAuth` | `useAuthStore` + `authService` | `login()`, `logout()`, `checkSession()` |
| `useProject` | `useProjectStore` + `projectService` | project selection |
| `usePermission` | `usePermissionStore` + `projectService` | `hasPermission()`, `loadPermissions()` |
| `useNotification` | browser Notification API | `sendBrowserNotification()` |
| `useWebSocket` | native WebSocket | real-time messaging |

**Rules:**
- Zustand for **client state only** (auth, project, UI)
- **Server state** always uses `useApiQuery`/`useApiMutation` — never Zustand
- Never use `useEffect` for data fetching

## Auth Flow

1. Login → POST `/api/auth/login` → server sets `kactus_session_id` httpOnly cookie
2. `apiClient` uses `withCredentials: true` → browser sends cookie automatically
3. On 401 → interceptor redirects to `/login`
4. `AuthGuard` calls `useAuth().checkSession()` which calls `authService.me()` on mount
5. `useAuthStore` tracks `user` + `isAuthenticated` + `isLoading` — **no tokens in memory**
6. Project selection → `useProjectStore.setProject()` sets `kactus_project_id` cookie via `js-cookie`
7. Backend reads project cookie during auth → `request.state.project_id`
8. Permissions → `usePermission().loadPermissions(projectId)` calls `GET /api/me/permissions`
9. `ProjectGuard` restores project from cookie on mount, redirects to `/select-project` if missing

## Checklist

1. [ ] API calls defined in `services/` as object-style methods
2. [ ] New service exported from `services/index.ts`
3. [ ] Uses `useApiQuery`/`useApiMutation` wrappers (not raw TanStack Query)
4. [ ] Zustand used only for client state (auth, project, UI)
5. [ ] No tokens stored in localStorage — cookie-based auth
6. [ ] All API responses typed with `ApiResponse<T>`
