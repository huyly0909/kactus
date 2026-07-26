import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface DebugState {
  enabled: boolean;
  set: (v: boolean) => void;
  toggle: () => void;
}

/**
 * Debug-mode toggle (persisted). The stored flag is only *half* the gate —
 * `useDebugMode()` ANDs it with superuser status, so a non-admin flipping this
 * in localStorage still gets debug off. Turned on via the header Bug button or
 * the `?bugbug` query param (admin only).
 */
export const useDebugStore = create<DebugState>()(
  persist(
    (set) => ({
      enabled: false,
      set: (v) => set({ enabled: v }),
      toggle: () => set((s) => ({ enabled: !s.enabled })),
    }),
    { name: 'bloom-debug' },
  ),
);
