import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useUpdateZaloRecipients, useZaloChannelRecipients } from '@/hooks/useNotificationQuery';
import { ZaloConversationPicker, zaloRecipientKey } from './ZaloConversationPicker';
import { ZaloPAQRDialog } from './ZaloPAQRDialog';
import type { NotificationChannel, ZaloPAConfig, ZaloRecipient } from '@/types/notification';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  channel: NotificationChannel;
}

/** Saved targets from the channel config, tolerating the legacy single shape. */
function savedRecipients(config: ZaloPAConfig): ZaloRecipient[] {
  if (config.recipients?.length) {
    return config.recipients.map((r) => ({
      id: r.thread_id,
      name: r.name || r.thread_id,
      avatar: r.avatar,
      is_group: r.thread_type === 1,
    }));
  }
  if (config.thread_id) {
    return [
      {
        id: config.thread_id,
        name: config.recipient_name || config.thread_id,
        avatar: null,
        is_group: (config.thread_type ?? 0) === 1,
      },
    ];
  }
  return [];
}

/**
 * Re-select the conversations of an existing Zalo channel using its stored
 * credentials — no QR re-scan. A dead session surfaces as a fetch error with a
 * Reconnect shortcut (reauth keeps the saved recipients).
 */
export function ZaloRecipientsEditDialog({ open, onOpenChange, channel }: Props) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Map<string, ZaloRecipient>>(new Map());
  const [reauthOpen, setReauthOpen] = useState(false);

  const {
    data: recipients,
    isLoading,
    isError,
    refetch,
  } = useZaloChannelRecipients(open ? channel.id : '');
  const updateRecipients = useUpdateZaloRecipients(channel.id);

  // Pre-check what the channel already targets, fresh on every open.
  useEffect(() => {
    if (!open) return;
    setQuery('');
    setSelected(
      new Map(savedRecipients(channel.config as ZaloPAConfig).map((r) => [zaloRecipientKey(r), r])),
    );
  }, [open, channel]);

  const toggleRecipient = (recipient: ZaloRecipient) => {
    setSelected((prev) => {
      const next = new Map(prev);
      const key = zaloRecipientKey(recipient);
      if (next.has(key)) next.delete(key);
      else next.set(key, recipient);
      return next;
    });
  };

  const handleSave = async () => {
    const picked = [...selected.values()];
    if (picked.length === 0) return;
    await updateRecipients.mutateAsync(picked);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{t('notification.zalo.edit_conversations')}</DialogTitle>
        </DialogHeader>

        {isError ? (
          <div className="flex flex-col items-center gap-3 py-8">
            <AlertTriangle className="h-8 w-8 text-[var(--loss)]" />
            <p className="text-center text-sm text-muted-foreground">
              {t('notification.zalo.session_dead')}
            </p>
            <Button variant="outline" onClick={() => setReauthOpen(true)}>
              <RefreshCw className="mr-1 h-4 w-4" />
              {t('notification.zalo.reconnect')}
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              {t('notification.zalo.pick_hint_multi')}
            </p>
            <ZaloConversationPicker
              recipients={recipients}
              isLoading={isLoading}
              query={query}
              onQueryChange={setQuery}
              selected={selected}
              onToggle={toggleRecipient}
              disabled={updateRecipients.isPending}
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                {t('common.cancel')}
              </Button>
              <Button
                onClick={() => void handleSave()}
                disabled={selected.size === 0 || updateRecipients.isPending}
              >
                {updateRecipients.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                {t('common.save')}
              </Button>
            </div>
          </div>
        )}

        {reauthOpen && (
          <ZaloPAQRDialog
            open={reauthOpen}
            onOpenChange={setReauthOpen}
            mode="reauth"
            channelId={channel.id}
            onDone={() => {
              setReauthOpen(false);
              void refetch();
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
