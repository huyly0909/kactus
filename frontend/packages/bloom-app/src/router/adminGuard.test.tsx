import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AdminGuard } from './adminGuard';

// Mock authStore
const mockUseAuthStore = vi.fn();

vi.mock('@kactus-bloom/ui/stores', () => ({
  useAuthStore: () => mockUseAuthStore(),
}));

// Mock NotFoundPage since AdminGuard renders it for non-admins
vi.mock('../pages/NotFound', () => ({
  NotFoundPage: () => <div>Not Found Page</div>,
}));

function renderAdminGuard(initialEntry = '/admin/users') {
  return render(
    <MantineProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route element={<AdminGuard />}>
            <Route path="/admin/users" element={<div>Admin Users</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </MantineProvider>,
  );
}

describe('AdminGuard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders admin content for superusers', () => {
    mockUseAuthStore.mockReturnValue({
      user: { id: '1', email: 'admin@test.io', is_superuser: true },
      isAuthenticated: true,
    });

    renderAdminGuard();
    expect(screen.getByText('Admin Users')).toBeInTheDocument();
    expect(screen.queryByText('Not Found Page')).not.toBeInTheDocument();
  });

  it('renders 404 for non-superusers', () => {
    mockUseAuthStore.mockReturnValue({
      user: { id: '2', email: 'user@test.io', is_superuser: false },
      isAuthenticated: true,
    });

    renderAdminGuard();
    expect(screen.getByText('Not Found Page')).toBeInTheDocument();
    expect(screen.queryByText('Admin Users')).not.toBeInTheDocument();
  });

  it('renders 404 when not authenticated', () => {
    mockUseAuthStore.mockReturnValue({
      user: null,
      isAuthenticated: false,
    });

    renderAdminGuard();
    expect(screen.getByText('Not Found Page')).toBeInTheDocument();
    expect(screen.queryByText('Admin Users')).not.toBeInTheDocument();
  });
});
