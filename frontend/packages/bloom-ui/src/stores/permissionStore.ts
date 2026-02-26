import { create } from 'zustand';
import type { PermissionItem, PermissionAct } from '../types/auth';

interface PermissionState {
  permissions: PermissionItem[];
  role: string | null;
  isSuperuser: boolean;
  isLoading: boolean;
  setPermissions: (
    permissions: PermissionItem[],
    role: string | null,
    isSuperuser: boolean,
  ) => void;
  clearPermissions: () => void;
  setLoading: (loading: boolean) => void;
  hasPermission: (permission: string, act?: PermissionAct) => boolean;
}

/**
 * Permission store — tracks current user's permissions in the selected project.
 */
export const usePermissionStore = create<PermissionState>((set, get) => ({
  permissions: [],
  role: null,
  isSuperuser: false,
  isLoading: false,

  setPermissions: (permissions, role, isSuperuser) =>
    set({ permissions, role, isSuperuser, isLoading: false }),

  clearPermissions: () =>
    set({ permissions: [], role: null, isSuperuser: false, isLoading: false }),

  setLoading: (isLoading) => set({ isLoading }),

  hasPermission: (permission, act) => {
    if (get().isSuperuser) return true;
    return get().permissions.some((p) => p.permission === permission && (!act || p.act === act));
  },
}));
