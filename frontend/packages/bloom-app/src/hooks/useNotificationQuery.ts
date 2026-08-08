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
  telegramChats: (id: string) => [...notificationKeys.all, 'telegram-chats', id] as const,
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

// ---------------------------------------------------------------- Telegram
/** `getMe` on a not-yet-saved token. A mutation, not a query: the wizard fires
 * it on a button press and needs the result before it can advance a step. */
export function useTelegramVerify() {
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (botToken: string) => notificationService.telegram.verify(botToken),
    onError: () => toast.error(t('notification.telegram.verify_failed')),
  });
}

/** Chat discovery for a token the server has not stored yet. */
export function useTelegramDiscoverChats() {
  return useMutation({
    mutationFn: (botToken: string) => notificationService.telegram.discoverChats(botToken),
    // No toast: an empty result is the expected first run and the dialog
    // explains it far better than a toast could. Real failures surface inline.
  });
}

/** Resolve a hand-typed chat id or `@public_name`. */
export function useTelegramResolveChat() {
  const { t } = useTranslation();
  return useMutation({
    mutationFn: ({ botToken, chatId }: { botToken: string; chatId: string }) =>
      notificationService.telegram.resolveChat(botToken, chatId),
    onError: () => toast.error(t('notification.telegram.resolve_failed')),
  });
}

/** Chats reachable with an existing channel's stored token (re-pick picker). */
export function useTelegramChannelChats(channelId: string, enabled = true) {
  return useQuery({
    queryKey: notificationKeys.telegramChats(channelId),
    queryFn: () => notificationService.telegram.listChannelChats(channelId),
    enabled: !!channelId && enabled,
    retry: false, // a dead token errors — retrying only delays the hint
  });
}

/** Repoint a channel at a different chat (the bot token stays server-side). */
export function useTelegramUpdateChat(channelId: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (chatId: string) => notificationService.telegram.updateChat(channelId, chatId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notificationKeys.lists() });
      void qc.invalidateQueries({ queryKey: notificationKeys.detail(channelId) });
      toast.success(t('notification.telegram.chat_updated'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

/** ⚡ Send a real message to the configured chat. */
export function useTelegramTestMessage() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (channelId: string) => notificationService.telegram.testMessage(channelId),
    // Recorded in the send history either way — a failure is the interesting case.
    onSettled: (_data, _err, channelId) => {
      void qc.invalidateQueries({ queryKey: notificationKeys.logs(channelId) });
    },
    onSuccess: (_data, channelId) => {
      void qc.invalidateQueries({ queryKey: notificationKeys.detail(channelId) });
      toast.success(t('notification.telegram.test_sent_ok'));
    },
    onError: () => toast.error(t('notification.telegram.test_message_failed')),
  });
}

/** Replace the bot token (verified server-side before it is stored). */
export function useTelegramReauth(channelId: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (botToken: string) => notificationService.telegram.reauth(channelId, botToken),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: notificationKeys.lists() });
      void qc.invalidateQueries({ queryKey: notificationKeys.detail(channelId) });
      toast.success(t('notification.telegram.token_updated'));
    },
    onError: () => toast.error(t('notification.telegram.verify_failed')),
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
