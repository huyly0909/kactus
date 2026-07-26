import '@testing-library/jest-dom';
import { vi } from 'vitest';

// jsdom has no matchMedia; useMediaQuery reads it synchronously. Default to a
// non-matching query (min-width:768px → false → mobile tier). Tests that need a
// different result override with vi.stubGlobal('matchMedia', …).
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}
