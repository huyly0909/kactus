import { useAuthStore } from '../stores/authStore';
import { authService } from '../services/authService';

interface LoginPayload {
  email: string;
  password: string;
  remember?: boolean;
}

interface AuthUser {
  id: string;
  email: string;
  username: string;
  name: string;
  status: string;
}

interface AuthResult {
  user: AuthUser;
}

interface UseAuthReturn {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<AuthResult>;
  logout: () => Promise<void>;
  checkSession: () => Promise<void>;
}

/**
 * Auth hook — wraps authStore + authService for convenience.
 */
export const useAuth = (): UseAuthReturn => {
  const { user, isAuthenticated, isLoading, setUser, clearAuth, setLoading } = useAuthStore();

  const login = async (payload: LoginPayload): Promise<AuthResult> => {
    const result = await authService.login(payload);
    setUser(result.user);
    return result;
  };

  const logout = async () => {
    await authService.logout();
    clearAuth();
  };

  /** Check if user has an active session (call on app mount). */
  const checkSession = async () => {
    setLoading(true);
    try {
      const userData = await authService.me();
      setUser(userData);
    } catch {
      clearAuth();
    }
  };

  return {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    checkSession,
  };
};
