import { useCallback } from 'react';
import { usePermissionStore } from '../stores/permissionStore';
import { projectService } from '../services/projectService';
import type { PermissionAct, PermissionItem } from '../types/auth';

interface UsePermissionReturn {
  permissions: PermissionItem[];
  role: string | null;
  isSuperuser: boolean;
  isLoading: boolean;
  hasPermission: (permission: string, act?: PermissionAct) => boolean;
  loadPermissions: (projectId: string) => Promise<void>;
  clearPermissions: () => void;
}

/**
 * Permission hook — wraps permissionStore + projectService for convenience.
 */
export const usePermission = (): UsePermissionReturn => {
  const {
    permissions,
    role,
    isSuperuser,
    isLoading,
    hasPermission,
    setPermissions,
    clearPermissions,
    setLoading,
  } = usePermissionStore();

  const loadPermissions = useCallback(
    async (projectId: string) => {
      setLoading(true);
      try {
        const data = await projectService.getMyPermissions(projectId);
        setPermissions(data.permissions, data.role, data.is_superuser);
      } catch {
        clearPermissions();
      }
    },
    [setLoading, setPermissions, clearPermissions],
  );

  return {
    permissions,
    role,
    isSuperuser,
    isLoading,
    hasPermission,
    loadPermissions,
    clearPermissions,
  };
};
