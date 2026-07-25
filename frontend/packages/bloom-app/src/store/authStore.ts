import { create } from 'zustand';

interface User {
  id: string;
  email: string;
  username: string;
  name: string;
  status: string;
  is_superuser: boolean;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  clearAuth: () => void;
}

/**
 * Auth store — session is in httpOnly cookie (server-managed).
 * Frontend only tracks user info and authentication state.
 */
export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true, // true until /me check completes

  setUser: (user) => set({ user, isAuthenticated: user !== null, isLoading: false }),

  setLoading: (isLoading) => set({ isLoading }),

  clearAuth: () => set({ user: null, isAuthenticated: false, isLoading: false }),
}));
