import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LoginPage } from './';

// Mock useAuth hook
const mockLogin = vi.fn();
const mockUseAuth = vi.fn(() => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: mockLogin,
  logout: vi.fn(),
  checkSession: vi.fn(),
}));

vi.mock('@kactus-bloom/ui/hooks', () => ({
  useAuth: () => mockUseAuth(),
}));

function renderLogin() {
  return render(
    <MantineProvider>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/welcome" element={<div>Welcome Page</div>} />
        </Routes>
      </MemoryRouter>
    </MantineProvider>,
  );
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLogin.mockResolvedValue({ user: { id: '1', email: 'test@kactus.io' } });
  });

  it('renders the login form', () => {
    renderLogin();
    expect(screen.getByText('Kactus Bloom')).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /remember me/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('shows validation error for invalid email', async () => {
    renderLogin();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), 'not-an-email');
    await user.type(screen.getByLabelText(/password/i), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/valid email/i)).toBeInTheDocument();
    });
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('shows validation error for empty password', async () => {
    renderLogin();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), 'test@kactus.io');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeInTheDocument();
    });
    expect(mockLogin).not.toHaveBeenCalled();
  });

  it('calls login with valid credentials', async () => {
    renderLogin();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), 'test@kactus.io');
    await user.type(screen.getByLabelText(/password/i), 'Test123!');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'test@kactus.io',
        password: 'Test123!',
        remember: false,
      });
    });
  });

  it('passes remember=true when checkbox checked', async () => {
    renderLogin();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), 'test@kactus.io');
    await user.type(screen.getByLabelText(/password/i), 'Test123!');
    await user.click(screen.getByRole('checkbox', { name: /remember me/i }));
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'test@kactus.io',
        password: 'Test123!',
        remember: true,
      });
    });
  });

  it('shows error alert on login failure', async () => {
    mockLogin.mockRejectedValue(new Error('Invalid credentials'));
    renderLogin();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), 'test@kactus.io');
    await user.type(screen.getByLabelText(/password/i), 'wrong');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });
  });
});
