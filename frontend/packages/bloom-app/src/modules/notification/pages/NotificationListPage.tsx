import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Plus,
  Bell,
  Send,
  Hash,
  MessageCircle,
  RefreshCw,
  Zap,
  Loader2,
  FlaskConical,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  useNotificationChannels,
  useTelegramTestMessage,
  useTestChannel,
  useZaloTestMessage,
} from '@/hooks/useNotificationQuery';
import { ChannelFormDialog } from '@modules/notification/components/ChannelFormDialog';
import { TelegramSetupDialog } from '@modules/notification/components/telegram/TelegramSetupDialog';
import { ZaloPAQRDialog } from '@modules/notification/components/zalo/ZaloPAQRDialog';
import type { NotificationChannel, NotificationChannelType } from '@/types/notification';

const TYPE_ICON: Record<NotificationChannelType, React.ElementType> = {
  telegram: Send,
  slack: Hash,
  zalo_pa: MessageCircle,
};

interface RowActionProps {
  label: string;
  icon: React.ReactNode;
  disabled?: boolean;
  onClick: () => void;
}

/** Icon-only row action — the label lives in the tooltip so the actions column
 * stays narrow and every button reads the same way. */
function RowAction({ label, icon, disabled, onClick }: RowActionProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          aria-label={label}
          disabled={disabled}
          onClick={(e) => {
            e.stopPropagation(); // the row itself navigates to the detail page
            onClick();
          }}
        >
          {icon}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

export function NotificationListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: channels, isLoading } = useNotificationChannels();
  const zaloTest = useZaloTestMessage();
  const telegramTest = useTelegramTestMessage();
  const test = useTestChannel();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [reauthChannel, setReauthChannel] = useState<NotificationChannel | null>(null);
  const [tgReauthChannel, setTgReauthChannel] = useState<NotificationChannel | null>(null);

  const columns: DataTableColumn<NotificationChannel>[] = [
    {
      key: 'name',
      title: t('notification.name'),
      className: 'font-medium',
    },
    {
      key: 'channel_type',
      title: t('notification.channel_type'),
      render: (ch) => {
        const Icon = TYPE_ICON[ch.channel_type];
        return (
          <span className="flex items-center gap-2 text-muted-foreground">
            <Icon className="h-4 w-4" />
            {t(`notification.type_${ch.channel_type}`)}
          </span>
        );
      },
    },
    {
      key: 'is_active',
      title: t('notification.status'),
      render: (ch) => (
        <Badge variant={ch.is_active ? 'success' : 'secondary'}>
          {ch.is_active ? t('common.active') : t('common.inactive')}
        </Badge>
      ),
    },
    {
      key: 'actions',
      title: '',
      className: 'text-right',
      render: (ch) => {
        const isZalo = ch.channel_type === 'zalo_pa';
        const isTelegram = ch.channel_type === 'telegram';
        const zapping =
          (zaloTest.isPending && zaloTest.variables === ch.id) ||
          (telegramTest.isPending && telegramTest.variables === ch.id);
        const testing = test.isPending && test.variables === ch.id;
        return (
          <div className="flex items-center justify-end gap-1">
            {/* Credential check — every channel type has one, and it is the
                cheap thing to reach for before sending anything real. */}
            <RowAction
              label={t('notification.test')}
              disabled={test.isPending}
              onClick={() => test.mutate(ch.id)}
              icon={
                testing ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <FlaskConical className="h-3.5 w-3.5" />
                )
              }
            />
            {isZalo && (
              <RowAction
                label={t('notification.zalo.test_message')}
                disabled={!ch.is_active || zaloTest.isPending}
                onClick={() => zaloTest.mutate(ch.id)}
                icon={
                  zapping ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Zap className="h-3.5 w-3.5" />
                  )
                }
              />
            )}
            {isZalo && (
              <RowAction
                label={t('notification.zalo.reconnect')}
                onClick={() => setReauthChannel(ch)}
                icon={<RefreshCw className="h-3.5 w-3.5" />}
              />
            )}
            {/* Telegram gets the same pair: ⚡ is the only probe that proves the
                bot may post to the chat, and a @BotFather token can be revoked. */}
            {isTelegram && (
              <RowAction
                label={t('notification.telegram.test_message')}
                disabled={!ch.is_active || telegramTest.isPending}
                onClick={() => telegramTest.mutate(ch.id)}
                icon={
                  zapping ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Zap className="h-3.5 w-3.5" />
                  )
                }
              />
            )}
            {isTelegram && (
              <RowAction
                label={t('notification.telegram.reconnect')}
                onClick={() => setTgReauthChannel(ch)}
                icon={<RefreshCw className="h-3.5 w-3.5" />}
              />
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('notification.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('notification.subtitle')}</p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="mr-1 h-4 w-4" />
          {t('notification.create_title')}
        </Button>
      </div>

      {isLoading && <Skeleton className="h-40 w-full" />}

      {!isLoading && (channels?.length ?? 0) === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16 text-center">
          <Bell className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t('notification.empty_list')}</p>
        </div>
      )}

      {!isLoading && (channels?.length ?? 0) > 0 && (
        <DataTable
          columns={columns}
          data={channels ?? []}
          searchable
          searchPlaceholder={t('common.search')}
          getRowKey={(ch) => ch.id}
          onRowClick={(ch) => navigate(`/notifications/${ch.id}`)}
        />
      )}

      <ChannelFormDialog open={dialogOpen} onOpenChange={setDialogOpen} />

      {tgReauthChannel && (
        <TelegramSetupDialog
          open={!!tgReauthChannel}
          onOpenChange={(o) => !o && setTgReauthChannel(null)}
          mode="reauth"
          channelId={tgReauthChannel.id}
          onDone={() => setTgReauthChannel(null)}
        />
      )}

      {reauthChannel && (
        <ZaloPAQRDialog
          open={!!reauthChannel}
          onOpenChange={(o) => !o && setReauthChannel(null)}
          mode="reauth"
          channelId={reauthChannel.id}
          onDone={() => setReauthChannel(null)}
        />
      )}
    </div>
  );
}
