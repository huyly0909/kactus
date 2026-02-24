import { create } from 'zustand';
import type { User } from '../types';

interface AuthState {
    user: User | null;
    token: string | null;
    refreshToken: string | null;
    isAuthenticated: boolean;
    setUser: (user: User) => void;
    setToken: (token: string) => void;
    setRefreshToken: (refreshToken: string) => void;
    login: (user: User, token: string, refreshToken: string) => void;
    logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    user: null,
    token: null,
    refreshToken: null,
    isAuthenticated: false,

    setUser: (user) => set({ user }),
    setToken: (token) => set({ token }),
    setRefreshToken: (refreshToken) => set({ refreshToken }),

    login: (user, token, refreshToken) =>
        set({ user, token, refreshToken, isAuthenticated: true }),

    logout: () =>
        set({ user: null, token: null, refreshToken: null, isAuthenticated: false }),
}));
