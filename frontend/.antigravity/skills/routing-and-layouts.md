---
name: routing-and-layouts
description: Use when adding pages, routes, layout changes, or route guards. Covers React Router v7, Outlet-based layouts, and auth/admin/project guards.
---

# Routing & Layouts Skill

## Router Architecture

The router uses **React Router v7** with an **Outlet-based layout pattern**. Guards and layouts wrap routes via `<Route element={...}>` nesting:

```
Routes
├── AuthLayout (public)
│   └── /login
├── AuthGuard (protected)
│   ├── AdminGuard → AdminLayout
│   │   ├── /admin/users
│   │   ├── /admin/projects
│   │   └── /admin/authorization
│   └── MainLayout
│       ├── /select-project (no ProjectGuard)
│       └── ProjectGuard
│           ├── /welcome
│           └── /dashboard
├── / → redirect to /welcome
└── * → NotFoundPage
```

## Layouts

Both layouts use the shared `AppLayout` component from `@kactus-bloom/ui` with different sidebar configs:

| Layout | Routes | Description |
|--------|--------|-------------|
| `AuthLayout` | `/login` | Public, no sidebar |
| `AdminLayout` | `/admin/*` | Admin sidebar (Users, Projects, Authorization) |
| `MainLayout` | Everything else | User sidebar (Select Project, Dashboard, Reports, Settings) |

**Layout rules:**
- Layouts render `<Outlet />` for child routes
- `MainLayout` dynamically shows sidebar items based on project selection
- `MainLayout` checks `getProjectIdFromCookie()` synchronously for sidebar
- `ProjectGuard` handles actual data restoration
- Superusers see an "Admin Panel" link in `MainLayout`

## Route Guards

Guards render `<Outlet />` when the check passes, or redirect otherwise:

| Guard | File | Purpose | Redirect |
|-------|------|---------|----------|
| `AuthGuard` | `router/guards.tsx` | Calls `useAuth().checkSession()` on mount | → `/login` |
| `AdminGuard` | `router/adminGuard.tsx` | Checks `user.is_superuser` | → `NotFoundPage` |
| `ProjectGuard` | `router/projectGuard.tsx` | Restores project from cookie, validates membership | → `/select-project` |

Guard wrapping order (outermost → innermost):
```
AuthGuard → AdminGuard → AdminLayout (admin routes)
AuthGuard → MainLayout → ProjectGuard (project-scoped routes)
```

### AuthGuard Pattern (actual code)

```tsx
export const AuthGuard: FC = () => {
  const { isAuthenticated, isLoading, checkSession } = useAuth();
  const location = useLocation();

  useEffect(() => { checkSession(); }, []);

  if (isLoading) return <Center h="100vh"><Loader size="lg" /></Center>;
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />;
  return <Outlet />;
};
```

### ProjectGuard Pattern (actual code)

```tsx
export const ProjectGuard: FC = () => {
  const { currentProject, isLoading, setProject, clearProject, setLoading, getProjectIdFromCookie } =
    useProjectStore();

  useEffect(() => {
    // Reads cookie → fetches project list → finds matching project → setProject()
    // If cookie references unknown project → clearProject()
  }, []);

  if (isLoading) return <Center h="100vh"><Loader size="lg" /></Center>;
  if (!projectId && !currentProject) return <Navigate to="/select-project" ... />;
  return <Outlet />;
};
```

## Adding a New Page

### 1. Create the page component

```tsx
// bloom-app/src/pages/Analytics/index.tsx
import { type FC } from 'react';
import { Title, Text } from '@mantine/core';

export const AnalyticsPage: FC = () => {
  return (
    <>
      <Title order={2}>Analytics</Title>
      <Text>Analytics dashboard content</Text>
    </>
  );
};
```

### 2. Register in the router

```tsx
// bloom-app/src/router/index.tsx
import { AnalyticsPage } from '../pages/Analytics';

// Add inside the ProjectGuard group (project-scoped):
<Route element={<ProjectGuard />}>
  <Route path="/welcome" element={<WelcomePage />} />
  <Route path="/dashboard" element={<DashboardPage />} />
  <Route path="/analytics" element={<AnalyticsPage />} />  {/* ← add */}
</Route>
```

### 3. Add sidebar item in MainLayout

```tsx
// In bloom-app/src/layouts/MainLayout.tsx, inside navSections:
{ label: 'Analytics', icon: <BarChart3 size={18} />, href: '/analytics' },
```

## Page Structure Convention

Each page is a folder with `index.tsx`:

```
pages/
├── Dashboard/
│   └── index.tsx
├── Login/
│   ├── index.tsx
│   └── Login.test.tsx
├── Admin/
│   ├── index.tsx            # AdminLayout
│   ├── Users/index.tsx
│   ├── Projects/index.tsx
│   └── Authorization/index.tsx
├── ProjectSelect/
│   └── index.tsx
├── Welcome/
│   ├── index.tsx
│   └── Welcome.test.tsx
└── NotFound/
    ├── index.tsx
    └── NotFound.test.tsx
```

## Checklist

1. [ ] Page component uses named export
2. [ ] Route registered in `router/index.tsx` in correct layout/guard group
3. [ ] Wrapped with appropriate guard (AuthGuard, AdminGuard, or ProjectGuard)
4. [ ] Sidebar item added in the correct layout
5. [ ] Test file colocated (e.g. `PageName.test.tsx`)
