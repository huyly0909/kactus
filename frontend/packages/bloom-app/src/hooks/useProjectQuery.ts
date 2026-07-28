import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { projectService, type AddMemberPayload } from '@/services/projectService';
import type { ProjectStatus } from '@/types/project';

/** Query key factory — the single source of cache keys for the feature. */
export const projectKeys = {
  all: ['projects'] as const,
  lists: () => [...projectKeys.all, 'list'] as const,
  detail: (id: string) => [...projectKeys.all, 'detail', id] as const,
  members: (id: string) => [...projectKeys.all, 'members', id] as const,
};

// ----------------------------------------------------------------- queries
export function useProjects() {
  return useQuery({
    queryKey: projectKeys.lists(),
    queryFn: projectService.getProjects,
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: projectKeys.detail(id),
    queryFn: () => projectService.getProjectById(id),
    enabled: !!id,
  });
}

export function useProjectMembers(id: string) {
  return useQuery({
    queryKey: projectKeys.members(id),
    queryFn: () => projectService.getMembers(id),
    enabled: !!id,
  });
}

// --------------------------------------------------------------- mutations
export function useCreateProject() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (body: { name: string; code: string; description?: string }) =>
      projectService.createProject(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: projectKeys.lists() });
      toast.success(t('common.create_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

export function useUpdateProject(projectId: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (body: {
      name?: string;
      code?: string;
      description?: string;
      status?: ProjectStatus;
    }) => projectService.updateProject(projectId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: projectKeys.all });
      toast.success(t('common.update_success'));
    },
    // Surface the backend's own message — a member without manage rights gets a 403.
    onError: (err: unknown) => toast.error(resolveError(err, t('common.error_generic'))),
  });
}

export function useAddMember(projectId: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (payload: AddMemberPayload) => projectService.addMember(projectId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: projectKeys.members(projectId) });
      toast.success(t('projects.member_added'));
    },
    // Surface the backend's own message (e.g. generic 404, owner-grant 403, dup 409).
    onError: (err: unknown) => toast.error(resolveError(err, t('projects.member_add_error'))),
  });
}

export function useAssignOwner(projectId: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (email: string) => projectService.assignOwner(projectId, email),
    onSuccess: () => {
      // `projectKeys.all`, not just `members`: the owner column on the list and
      // the detail page's `has_owner` both change with this.
      void qc.invalidateQueries({ queryKey: projectKeys.all });
      toast.success(t('projects.owner_assigned'));
    },
    onError: (err: unknown) => toast.error(resolveError(err, t('projects.owner_assign_error'))),
  });
}

export function useUpdateMemberRole(projectId: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      projectService.updateMemberRole(projectId, userId, role),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: projectKeys.members(projectId) });
      toast.success(t('common.update_success'));
    },
    onError: (err: unknown) => toast.error(resolveError(err, t('common.error_generic'))),
  });
}

export function useRemoveMember(projectId: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (userId: string) => projectService.removeMember(projectId, userId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: projectKeys.members(projectId) });
      toast.success(t('projects.member_removed'));
    },
    onError: (err: unknown) => toast.error(resolveError(err, t('common.error_generic'))),
  });
}

/** Pull the API envelope's `message` off an axios error, else fall back. */
function resolveError(err: unknown, fallback: string): string {
  const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
  return message ?? fallback;
}
