import { create } from 'zustand';

// Drives the mobile navigation drawer (the sidebar rendered as a Sheet below
// md). Kept in a store — not local state in DashboardLayout — so the hamburger
// in TopHeader can toggle it without prop-drilling through the layout tree.
// Not persisted: the drawer always starts closed on load.
interface NavState {
  open: boolean;
  setOpen: (open: boolean) => void;
  close: () => void;
  toggle: () => void;
}

export const useNavStore = create<NavState>((set) => ({
  open: false,
  setOpen: (open) => set({ open }),
  close: () => set({ open: false }),
  toggle: () => set((s) => ({ open: !s.open })),
}));
