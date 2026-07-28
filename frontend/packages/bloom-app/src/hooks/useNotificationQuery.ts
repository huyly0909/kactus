import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  notificationService,
  type CreateChannelBody,
  type UpdateChannelBody,
} from '@/services/notificationService';
import type { NotificationEvent, ZaloRecipient } from '@/types/notification';

/** Query key factory — the single source of cache keys for the feature. */
export const notificationKeys = {
  all: ['notifications'] as const,
  lists: () => [...notificationKeys.all, 'list'] as const,
  detail: (id: string) => [...notificationKeys.all, 'detail', id] as const,
  logs: (id: string) => [...notificationKeys.all, 'logs', id] as const,
  // Deliberately NOT keyed by the search text: one Zalo directory fetch costs
  // three sequential round-trips upstream, so the list is fetched whole and
  // filtered in the browser.
  recipients: (sid: string) => [...notificationKeys.all, 'zalo-recipients', sid] as const,
  channelRecipients: (id: string) =>
    [...notificationKeys.all, 'zalo-channel-recipients', id] as const,
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

/** Every conversation on the freshly-scanned account. Fetched once, filtered locally. */
export function useZaloRecipients(sessionId: string) {
  return useQuery({
    queryKey: notificationKeys.recipients(sessionId),
    queryFn: () => notificationService.zaloPa.listRecipients(sessionId),
    enabled: !!sessionId,
  });
}

/** Conversations reachable with a channel's stored session (edit picker). */
export function useZaloChannelRecipients(channelId: string) {
  return useQuery({
    queryKey: notificationKeys.channelRecipients(channelId),
    queryFn: () => notificationService.zaloPa.listChannelRecipients(channelId),
    enabled: !!channelId,
    retry: false, // a dead session 502s — retrying only delays the reconnect hint
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
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (id: string) => notificationService.test(id),
    // The probe is recorded in the send history either way, so refresh it on
    // failure too — a failed test is exactly what the user wants to look at.
    onSettled: (_data, _err, id) => {
      void qc.invalidateQueries({ queryKey: notificationKeys.logs(id) });
    },
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
    mutationFn: (body: { session_id: string; name: string; recipients: ZaloRecipient[] }) =>
      notificationService.zaloPa.createChannel(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notificationKeys.lists() });
      toast.success(t('common.create_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

/** Replace a zalo channel's saved conversations (no QR re-scan). */
export function useUpdateZaloRecipients(channelId: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (recipients: ZaloRecipient[]) =>
      notificationService.zaloPa.updateRecipients(channelId, recipients),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notificationKeys.lists() });
      void qc.invalidateQueries({ queryKey: notificationKeys.detail(channelId) });
      toast.success(t('notification.zalo.recipients_updated'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

/** ⚡ Send "Hello, nice to meet you" to every saved conversation. */
export function useZaloTestMessage() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (channelId: string) => notificationService.zaloPa.testMessage(channelId),
    onSettled: (_data, _err, channelId) => {
      void qc.invalidateQueries({ queryKey: notificationKeys.logs(channelId) });
    },
    onSuccess: (result, channelId) => {
      void qc.invalidateQueries({ queryKey: notificationKeys.detail(channelId) });
      if (result.failed > 0) {
        toast.warning(
          t('notification.zalo.test_sent', { sent: result.sent, failed: result.failed }),
        );
      } else {
        toast.success(t('notification.zalo.test_sent_ok', { sent: result.sent }));
      }
    },
    onError: () => toast.error(t('notification.zalo.test_message_failed')),
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
