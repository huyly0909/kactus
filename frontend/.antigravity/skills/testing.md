---
name: testing
description: Use when writing, running, or debugging tests. Covers Vitest + React Testing Library patterns and conventions for the bloom monorepo.
---

# Testing Skill

## Framework

- **Vitest** — test runner
- **React Testing Library** — component testing
- **jsdom** — browser environment simulation

## Running Tests

```bash
pnpm test              # run all tests once (via Turborepo)
pnpm test:watch        # watch mode during development
```

## Test File Convention

Colocate test files with source using `*.test.tsx` suffix:

```
pages/Login/index.tsx
pages/Login/Login.test.tsx
pages/Welcome/index.tsx
pages/Welcome/Welcome.test.tsx
router/guards.tsx
router/guards.test.tsx
router/adminGuard.tsx
router/adminGuard.test.tsx
router/projectGuard.tsx
router/projectGuard.test.tsx
```

## Component Test Pattern

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UserCard } from './UserCard';

describe('UserCard', () => {
  it('renders user name and balance', () => {
    render(<UserCard name="Alice" balance={1500} />);

    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('$1,500')).toBeInTheDocument();
  });

  it('handles click event', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();

    render(<UserCard name="Alice" balance={1500} onClick={onClick} />);
    await user.click(screen.getByRole('button'));

    expect(onClick).toHaveBeenCalledOnce();
  });
});
```

## Testing with Providers

For components that depend on context (React Router, TanStack Query):

```tsx
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const renderWithProviders = (ui: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  );
};
```

## Guard Test Pattern (actual code)

Guards use the `Outlet` pattern, so test with `Routes`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, Outlet } from 'react-router-dom';

// Mock the hook used by the guard
vi.mock('@kactus-bloom/ui/hooks', () => ({
  useAuth: vi.fn(),
}));

describe('AuthGuard', () => {
  it('redirects to /login when not authenticated', async () => {
    const { useAuth } = await import('@kactus-bloom/ui/hooks');
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      checkSession: vi.fn(),
      // ... other fields
    });

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route element={<AuthGuard />}>
            <Route path="/dashboard" element={<div>Dashboard</div>} />
          </Route>
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Login Page')).toBeInTheDocument();
    });
  });

  it('renders child route when authenticated', async () => {
    vi.mocked(useAuth).mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      checkSession: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route element={<AuthGuard />}>
            <Route path="/dashboard" element={<div>Dashboard</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument();
    });
  });
});
```

## Mocking Stores

When testing components that use Zustand stores:

```tsx
vi.mock('@kactus-bloom/ui/stores', () => ({
  useAuthStore: vi.fn(() => ({
    user: { id: '1', email: 'test@test.com', is_superuser: false },
    isAuthenticated: true,
    isLoading: false,
  })),
  useProjectStore: vi.fn(() => ({
    currentProject: { id: '1', name: 'Test Project' },
    getProjectIdFromCookie: () => '1',
  })),
}));
```

## Checklist

1. **Write tests** for all new components, hooks, guards, and pages
2. **Update tests** when modifying existing code
3. **Run tests** before committing: `pnpm test`
4. **Colocate** test files with source (`*.test.tsx`)
5. **Use** `userEvent` for interactions (not `fireEvent`)
6. **Use** `screen` queries for assertions
7. **Wrap** with `MemoryRouter` + `QueryClientProvider` (+ i18next `I18nextProvider` if the component uses `useTranslation`) when needed
8. **Mock** store/hook imports with `vi.mock('@kactus-bloom/ui/hooks')` or `/stores`
