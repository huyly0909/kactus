import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  notificationService,
  type CreateChannelBody,
  type UpdateChannelBody,
} from '@/services/notificationService';
import type { NotificationEvent } from '@/types/notification';

/** Query key factory — the single source of cache keys for the feature. */
export const notificationKeys = {
  all: ['notifications'] as const,
  lists: () => [...notificationKeys.all, 'list'] as const,
  detail: (id: string) => [...notificationKeys.all, 'detail', id] as const,
  logs: (id: string) => [...notificationKeys.all, 'logs', id] as const,
  recipients: (sid: string, q: string) =>
    [...notificationKeys.all, 'zalo-recipients', sid, q] as const,
};

// ----------------------------------------------------------------- queries
export function useNotificationChannels() {
  return useQuery({
    queryKey: notificationKeys.lists(),
    queryFn: notificationService.list,
  });
}

export function useNotificationChannel(id: string) {
  return useQuery({
    queryKey: notificationKeys.detail(id),
    queryFn: () => notificationService.get(id),
    enabled: !!id,
  });
}

export function useNotificationLogs(id: string) {
  return useQuery({
    queryKey: notificationKeys.logs(id),
    queryFn: () => notificationService.logs(id),
    enabled: !!id,
  });
}

export function useZaloRecipients(sessionId: string, query: string) {
  return useQuery({
    queryKey: notificationKeys.recipients(sessionId, query),
    queryFn: () => notificationService.zaloPa.listRecipients(sessionId, query),
    enabled: !!sessionId,
  });
}

// --------------------------------------------------------------- mutations
export function useCreateChannel() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (body: CreateChannelBody) => notificationService.create(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notificationKeys.lists() });
      toast.success(t('common.create_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

export function useUpdateChannel(id: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (body: UpdateChannelBody) => notificationService.update(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notificationKeys.lists() });
      void qc.invalidateQueries({ queryKey: notificationKeys.detail(id) });
      toast.success(t('common.update_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

export function useDeleteChannel() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (id: string) => notificationService.remove(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notificationKeys.lists() });
      toast.success(t('common.delete_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

export function useTestChannel() {
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (id: string) => notificationService.test(id),
    onSuccess: () => toast.success(t('notification.test_ok')),
    onError: () => toast.error(t('notification.test_failed')),
  });
}

export function useSendChannel(id: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (event: NotificationEvent) => notificationService.send(id, event),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notificationKeys.logs(id) });
      toast.success(t('notification.send_ok'));
    },
    onError: () => toast.error(t('notification.send_failed')),
  });
}

export function useCreateZaloChannel() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (body: {
      session_id: string;
      name: string;
      thread_id: string;
      thread_type: number;
      recipient_name?: string;
    }) => notificationService.zaloPa.createChannel(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notificationKeys.lists() });
      toast.success(t('common.create_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

export function useReauthZaloChannel() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: ({ channelId, sessionId }: { channelId: string; sessionId: string }) =>
      notificationService.zaloPa.reauth(channelId, sessionId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notificationKeys.lists() });
      toast.success(t('notification.reauth_ok'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}
