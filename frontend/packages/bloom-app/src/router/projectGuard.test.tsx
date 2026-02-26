import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ProjectGuard } from './projectGuard';

// Mock stores and services
const mockUseProjectStore = vi.fn();
const mockGetProjectById = vi.fn();

vi.mock('@kactus-bloom/ui/stores', () => ({
  useProjectStore: () => mockUseProjectStore(),
}));

vi.mock('@kactus-bloom/ui/services', () => ({
  projectService: {
    getProjectById: (...args: unknown[]) => mockGetProjectById(...args),
  },
}));

function renderProjectGuard(initialEntry = '/dashboard') {
  return render(
    <MantineProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route element={<ProjectGuard />}>
            <Route path="/dashboard" element={<div>Dashboard</div>} />
          </Route>
          <Route path="/select-project" element={<div>Select Project</div>} />
        </Routes>
      </MemoryRouter>
    </MantineProvider>,
  );
}

describe('ProjectGuard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('redirects to /select-project when no project cookie', () => {
    mockUseProjectStore.mockReturnValue({
      currentProject: null,
      isLoading: false,
      setProject: vi.fn(),
      setLoading: vi.fn(),
      getProjectIdFromCookie: () => undefined,
    });

    renderProjectGuard();
    expect(screen.getByText('Select Project')).toBeInTheDocument();
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument();
  });

  it('shows loader while loading project from cookie', () => {
    mockUseProjectStore.mockReturnValue({
      currentProject: null,
      isLoading: true,
      setProject: vi.fn(),
      setLoading: vi.fn(),
      getProjectIdFromCookie: () => '123',
    });

    renderProjectGuard();
    // Loader is shown, neither dashboard nor select-project visible
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument();
    expect(screen.queryByText('Select Project')).not.toBeInTheDocument();
  });

  it('renders content when project is loaded', () => {
    mockUseProjectStore.mockReturnValue({
      currentProject: { id: '123', name: 'Test Project', code: 'TP', status: 'active' },
      isLoading: false,
      setProject: vi.fn(),
      setLoading: vi.fn(),
      getProjectIdFromCookie: () => '123',
    });

    renderProjectGuard();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.queryByText('Select Project')).not.toBeInTheDocument();
  });
});
