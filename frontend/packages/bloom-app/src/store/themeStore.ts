import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type ThemeMode = 'light' | 'dark';

// 'default' keeps kactus's own indigo base (no `theme-*` class). The rest are
// Builtiful presets: zinc/blue/emerald/violet/orange recolor the accent only;
// navy/plum/copper are tinted-chrome presets that also re-skin surfaces + the
// sidebar. See the `.theme-*` blocks in index.css.
export type ThemeColor =
  | 'default'
  | 'zinc'
  | 'blue'
  | 'emerald'
  | 'violet'
  | 'orange'
  | 'navy'
  | 'plum'
  | 'copper';
export type ThemeRadius = 'sharp' | 'classic' | 'smooth';
// Manual display-size nudge on top of the auto viewport clamp — drives the
// `.scale-*` atoms which set --font-scale (see index.css).
export type ThemeScale = 'compact' | 'normal' | 'large' | 'xl';

interface ThemeState {
  mode: ThemeMode;
  color: ThemeColor;
  radius: ThemeRadius;
  scale: ThemeScale;
  setMode: (mode: ThemeMode) => void;
  setColor: (color: ThemeColor) => void;
  setRadius: (radius: ThemeRadius) => void;
  setScale: (scale: ThemeScale) => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      // kactus is dark-first fintech; the indigo base is `default`.
      mode: 'dark',
      color: 'default',
      radius: 'smooth',
      scale: 'normal',
      setMode: (mode) => set({ mode }),
      setColor: (color) => set({ color }),
      setRadius: (radius) => set({ radius }),
      setScale: (scale) => set({ scale }),
    }),
    { name: 'bloom-theme-v1' },
  ),
);
