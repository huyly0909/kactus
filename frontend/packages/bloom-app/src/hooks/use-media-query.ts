// useMediaQuery — subscribe to a CSS media query from React. Powers JS-side
// responsive branches (e.g. the DataTable renders cards below `md` instead of
// the table) where CSS-only hiding would leave the heavy hidden variant mounted.
// SPA-only (no SSR): the first snapshot reads matchMedia synchronously.

import { useSyncExternalStore } from 'react';

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mql = window.matchMedia(query);
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    },
    () => window.matchMedia(query).matches,
  );
}

/** True from Tailwind's `md` breakpoint (768px) up — the table/desktop tier. */
export function useIsDesktop(): boolean {
  return useMediaQuery('(min-width: 768px)');
}
