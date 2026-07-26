import { useAuthStore } from '@/store/authStore';
import { useProjectStore } from '@/store/projectStore';
import { authService } from '@/services/authService';
import { projectService } from '@/services/projectService';
import { setLanguage } from '@/i18n';

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
  is_superuser: boolean;
  language?: string | null;
  timezone?: string | null;
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
/**
 * Select an active project so the project-scoped API works immediately.
 *
 * Scoped endpoints 403 with "No project selected" when the `kactus_project_id`
 * cookie is unset, so on session start we resolve one: keep the cookie's choice
 * if it is still a project the user belongs to, else the personal project
 * (deterministic `user-<id>` code), else the first membership. Superusers hold
 * no personal project and bypass scoping, so they are skipped. Best-effort:
 * failure just leaves the pages to prompt for a selection.
 */
/**
 * Apply the user's saved UI language. Preferences are user-scoped (persisted on
 * the account via PATCH /api/auth/me), so the account — not localStorage — is the
 * source of truth. No-op when the user has no language set (keeps the i18n default).
 */
const applyUserLanguage = (authUser: AuthUser): void => {
  if (authUser.language) void setLanguage(authUser.language);
};

const hydrateActiveProject = async (authUser: AuthUser): Promise<void> => {
  if (authUser.is_superuser) return;
  try {
    const { items } = await projectService.getProjects();
    if (items.length === 0) return;
    const store = useProjectStore.getState();
    const cookieId = store.getProjectIdFromCookie();
    const selected =
      items.find((p) => p.id === cookieId) ??
      items.find((p) => p.code === `user-${authUser.id}`) ??
      items[0];
    store.setProject(selected);
  } catch {
    /* non-fatal — the Projects page lets the user pick manually */
  }
};

export const useAuth = (): UseAuthReturn => {
  const { user, isAuthenticated, isLoading, setUser, clearAuth, setLoading } = useAuthStore();

  const login = async (payload: LoginPayload): Promise<AuthResult> => {
    const result = await authService.login(payload);
    setUser(result.user);
    applyUserLanguage(result.user);
    await hydrateActiveProject(result.user);
    return result;
  };

  const logout = async () => {
    await authService.logout();
    useProjectStore.getState().clearProject();
    clearAuth();
  };

  /** Check if user has an active session (call on app mount). */
  const checkSession = async () => {
    setLoading(true);
    try {
      const userData = await authService.me();
      setUser(userData);
      applyUserLanguage(userData);
      await hydrateActiveProject(userData);
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
