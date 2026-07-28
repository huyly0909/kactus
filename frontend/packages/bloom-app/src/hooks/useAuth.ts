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
 * Apply the user's saved UI language. Preferences are user-scoped (persisted on
 * the account via PATCH /api/auth/me), so the account — not localStorage — is the
 * source of truth. No-op when the user has no language set (keeps the i18n default).
 */
const applyUserLanguage = (authUser: AuthUser): void => {
  if (authUser.language) void setLanguage(authUser.language);
};

/**
 * Resolve the active project on every session start.
 *
 * The `kactus_project_id` cookie is both the local cache (survives refresh) and
 * the transport — the backend reads it to scope every query — so it is always
 * validated against the memberships actually returned, never trusted blind: a
 * project that was deleted, or a cookie left behind by another account or a
 * wiped database, would otherwise keep scoping requests to a dead id.
 *
 * Order: the cookie's choice if still valid → the first project this user
 * created (their auto-provisioned "First Project" on a first-ever login) → the
 * first membership. Superusers own no project and default to the unscoped
 * cross-project view, but a project they picked explicitly is restored.
 * Best-effort: on failure the pages prompt for a selection.
 */
const hydrateActiveProject = async (authUser: AuthUser): Promise<void> => {
  try {
    const { items } = await projectService.getProjects();
    const store = useProjectStore.getState();

    const fromCookie = items.find((p) => p.id === store.getProjectIdFromCookie());
    if (fromCookie) {
      store.setProject(fromCookie);
      return;
    }
    if (items.length === 0 || authUser.is_superuser) {
      store.clearProject();
      return;
    }
    store.setProject(items.find((p) => p.created_by === authUser.id) ?? items[0]);
  } catch {
    /* non-fatal — the Projects page lets the user pick manually */
  } finally {
    // Always mark the attempt as settled, including the swallowed-error path:
    // `RequireProject` waits on this, and never flipping it would hang the
    // route on a spinner instead of offering the picker.
    useProjectStore.getState().setHydrated(true);
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
