import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { adminService } from '@/services/adminService';
import type { CreateUserPayload } from '@/types/admin';

/** Query key factory — the single source of cache keys for the admin feature. */
export const adminKeys = {
  all: ['admin'] as const,
  users: () => [...adminKeys.all, 'users'] as const,
  projects: () => [...adminKeys.all, 'projects'] as const,
  authorization: () => [...adminKeys.all, 'authorization'] as const,
};

// ----------------------------------------------------------------- queries
export function useAdminUsers() {
  return useQuery({
    queryKey: adminKeys.users(),
    queryFn: adminService.getUsers,
  });
}

export function useAdminProjects() {
  return useQuery({
    queryKey: adminKeys.projects(),
    queryFn: adminService.getAllProjects,
  });
}

export function useAdminAuthorization() {
  return useQuery({
    queryKey: adminKeys.authorization(),
    queryFn: adminService.getAuthorization,
  });
}

// --------------------------------------------------------------- mutations
export function useCreateUser() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (payload: CreateUserPayload) => adminService.createUser(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: adminKeys.users() });
      toast.success(t('common.create_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

export function useUpdateUserRole() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: ({ userId, isSuperuser }: { userId: string; isSuperuser: boolean }) =>
      adminService.updateUserRole(userId, { is_superuser: isSuperuser }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: adminKeys.users() });
      toast.success(t('common.update_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

/**
 * Resets a user's password. The generated password comes back in the result and
 * is shown once by the caller — deliberately not toasted.
 */
export function useResetPassword() {
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (userId: string) => adminService.resetPassword(userId),
    onError: () => toast.error(t('common.error_generic')),
  });
}

export function useDeactivateUser() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (userId: string) => adminService.deactivateUser(userId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: adminKeys.users() });
      toast.success(t('admin.users.deactivate_ok'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}
