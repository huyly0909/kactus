import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Plus, Bell, Send, Hash, MessageCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { useNotificationChannels } from '@/hooks/useNotificationQuery';
import { ChannelFormDialog } from '@modules/notification/components/ChannelFormDialog';
import { ZaloPAQRDialog } from '@modules/notification/components/ZaloPAQRDialog';
import type { NotificationChannel, NotificationChannelType } from '@/types/notification';

const TYPE_ICON: Record<NotificationChannelType, React.ElementType> = {
  telegram: Send,
  slack: Hash,
  zalo_pa: MessageCircle,
};

export function NotificationListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: channels, isLoading } = useNotificationChannels();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [reauthChannel, setReauthChannel] = useState<NotificationChannel | null>(null);

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
      render: (ch) =>
        ch.channel_type === 'zalo_pa' ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              setReauthChannel(ch);
            }}
          >
            <RefreshCw className="mr-1 h-3.5 w-3.5" />
            {t('notification.zalo.reconnect')}
          </Button>
        ) : null,
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
