/**
 * Design tokens for the shadcn/Tailwind era.
 *
 * The Mantine `MantineThemeOverride` is gone — theming now lives in CSS
 * variables (see the consuming app's `index.css` `@theme` block). This plain,
 * framework-agnostic object keeps the brand scale available to JS (e.g. chart
 * colors) without pulling in a UI-kit dependency.
 */
export const theme = {
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  defaultRadius: '0.625rem',
  /** Indigo brand scale (50 → 900) — matches the fintech primary. */
  brand: [
    '#eef2ff',
    '#e0e7ff',
    '#c7d2fe',
    '#a5b4fc',
    '#818cf8',
    '#6366f1',
    '#4f46e5',
    '#4338ca',
    '#3730a3',
    '#312e81',
  ],
} as const;
