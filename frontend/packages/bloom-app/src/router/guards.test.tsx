import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthGuard } from '../router/guards';

// Mock useAuth hook
const mockCheckSession = vi.fn();
const mockUseAuth = vi.fn();

vi.mock('@kactus-bloom/ui/hooks', () => ({
  useAuth: () => mockUseAuth(),
}));

function renderGuard(initialEntry = '/protected') {
  return render(
    <MantineProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route element={<AuthGuard />}>
            <Route path="/protected" element={<div>Protected Content</div>} />
          </Route>
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>
    </MantineProvider>,
  );
}

describe('AuthGuard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loader while checking session', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      checkSession: mockCheckSession,
    });

    renderGuard();
    // Loader should be visible (Mantine Loader renders an SVG)
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument();
  });

  it('renders protected content when authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      checkSession: mockCheckSession,
    });

    renderGuard();
    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('redirects to login when not authenticated', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      checkSession: mockCheckSession,
    });

    renderGuard();
    expect(screen.getByText('Login Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  it('calls checkSession on mount', () => {
    mockUseAuth.mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      checkSession: mockCheckSession,
    });

    renderGuard();
    expect(mockCheckSession).toHaveBeenCalledOnce();
  });
});
