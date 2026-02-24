import { useAuthStore } from '../stores/authStore';
import { authService } from '../services/authService';
import type { LoginRequest } from '../types';

/**
 * Auth hook — provides login, logout, and auth state.
 * Wraps the Zustand auth store + authService API calls.
 */
export const useAuth = () => {
    const { user, isAuthenticated, login: storeLogin, logout: storeLogout } = useAuthStore();

    const login = async (credentials: LoginRequest) => {
        const { data } = await authService.login(credentials);
        const { user, tokens } = data.data;
        storeLogin(user, tokens.accessToken, tokens.refreshToken);
        return user;
    };

    const logout = async () => {
        try {
            await authService.logout();
        } finally {
            storeLogout();
        }
    };

    return { user, isAuthenticated, login, logout };
};
