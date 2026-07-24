import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { useNotificationLogs } from '@/hooks/useNotificationQuery';
import type { NotificationLog } from '@/types/notification';

interface Props {
  channelId: string;
}

/** Send history for a channel — most-recent-first, searchable + paginated. */
export function ChannelLogTable({ channelId }: Props) {
  const { t } = useTranslation();
  const { data: logs, isLoading } = useNotificationLogs(channelId);

  const columns: DataTableColumn<NotificationLog>[] = [
    {
      key: 'event_title',
      title: t('notification.log.event'),
      render: (log) => (
        <>
          <div className="font-medium">{log.event_title}</div>
          {log.error && (
            <div className="truncate text-xs text-[var(--loss)]" title={log.error}>
              {log.error}
            </div>
          )}
        </>
      ),
    },
    {
      key: 'status',
      title: t('notification.log.status'),
      render: (log) => (
        <Badge variant={log.status === 'success' ? 'success' : 'danger'}>
          {t(`notification.status_${log.status}`)}
        </Badge>
      ),
    },
    {
      key: 'attempts',
      title: t('notification.log.attempts'),
      className: 'text-muted-foreground',
    },
    {
      key: 'started_at',
      title: t('notification.log.time'),
      className: 'text-xs text-muted-foreground',
      render: (log) => (log.started_at ? new Date(log.started_at).toLocaleString() : '—'),
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={logs ?? []}
      loading={isLoading}
      searchable
      searchPlaceholder={t('common.search')}
      emptyMessage={t('notification.no_logs')}
      getRowKey={(log) => log.id}
    />
  );
}
