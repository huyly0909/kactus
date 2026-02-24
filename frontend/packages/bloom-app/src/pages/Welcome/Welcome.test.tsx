import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { WelcomePage } from './';

// Mock useAuth hook
vi.mock('@kactus-bloom/ui/hooks', () => ({
  useAuth: () => ({
    user: { id: '1', email: 'test@kactus.io', name: 'Test User' },
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    checkSession: vi.fn(),
  }),
}));

function renderWelcome() {
  return render(
    <MantineProvider>
      <WelcomePage />
    </MantineProvider>,
  );
}

describe('WelcomePage', () => {
  it('renders the welcome title', () => {
    renderWelcome();
    expect(screen.getByText('Welcome to Kactus Fin')).toBeInTheDocument();
  });

  it('greets the user by name', () => {
    renderWelcome();
    expect(screen.getByText(/hello, test user/i)).toBeInTheDocument();
  });

  it('shows navigation hint', () => {
    renderWelcome();
    expect(screen.getByText(/sidebar to navigate/i)).toBeInTheDocument();
  });
});
