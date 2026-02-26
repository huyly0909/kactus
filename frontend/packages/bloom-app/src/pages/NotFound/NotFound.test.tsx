import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { NotFoundPage } from './index';

function renderNotFound() {
  return render(
    <MantineProvider>
      <MemoryRouter initialEntries={['/some-missing-page']}>
        <Routes>
          <Route path="*" element={<NotFoundPage />} />
          <Route path="/" element={<div>Home Page</div>} />
        </Routes>
      </MemoryRouter>
    </MantineProvider>,
  );
}

describe('NotFoundPage', () => {
  it('renders 404 text', () => {
    renderNotFound();
    expect(screen.getByText('404')).toBeInTheDocument();
    expect(screen.getByText('Page Not Found')).toBeInTheDocument();
  });

  it('has a Go Home button', () => {
    renderNotFound();
    expect(screen.getByText('Go Home')).toBeInTheDocument();
  });

  it('navigates to home on button click', () => {
    renderNotFound();
    const button = screen.getByText('Go Home');
    fireEvent.click(button);
    expect(screen.getByText('Home Page')).toBeInTheDocument();
  });
});
