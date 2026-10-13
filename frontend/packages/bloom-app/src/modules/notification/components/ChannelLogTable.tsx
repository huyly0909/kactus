import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useFormatDateTime } from '@/hooks/useFormatDateTime';
import { useNotificationLogs } from '@/hooks/useNotificationQuery';
import { LogDetailDialog } from './LogDetailDialog';
import type { NotificationLevel, NotificationLog } from '@/types/notification';

interface Props {
  channelId: string;
}

const LEVEL_VARIANT: Record<NotificationLevel, 'secondary' | 'warning' | 'danger'> = {
  info: 'secondary',
  warning: 'warning',
  critical: 'danger',
};

/** `2/3`, with the conversation names on hover. Blank for single-target channels. */
function RecipientsCell({ log }: { log: NotificationLog }) {
  const { t } = useTranslation();
  if (!log.targets.length) return <span className="text-muted-foreground">—</span>;

  const delivered = log.delivered_count ?? log.targets.filter((tg) => tg.ok).length;
  const total = log.target_count ?? log.targets.length;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={
            delivered === total ? 'tabular-nums' : 'tabular-nums font-medium text-[var(--warning)]'
          }
        >
          {delivered}/{total}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <ul className="space-y-0.5 text-xs">
          {log.targets.map((tg) => (
            <li key={`${tg.thread_type}-${tg.thread_id}`}>
              {tg.ok ? '✓' : '✗'} {tg.name || tg.thread_id}
            </li>
          ))}
        </ul>
        <p className="mt-1 text-xs opacity-70">{t('notification.log.open_detail')}</p>
      </TooltipContent>
    </Tooltip>
  );
}

/** Send history for a channel — most-recent-first, searchable + paginated.
 *
 * A row is a summary; the per-conversation and per-attempt detail lives in the
 * dialog behind it (the row data already carries both — no extra fetch). */
export function ChannelLogTable({ channelId }: Props) {
  const { t } = useTranslation();
  const { data: logs, isLoading } = useNotificationLogs(channelId);
  const fmtDateTime = useFormatDateTime();
  const [selected, setSelected] = useState<NotificationLog | null>(null);

  const columns: DataTableColumn<NotificationLog>[] = [
    {
      key: 'event_title',
      title: t('notification.log.event'),
      // An unbroken error URL is wider than the card, and `truncate` in an
      // auto-layout table has nothing to truncate against — so the previews get
      // an explicit width and the columns after them stay on screen.
      render: (log) => (
        <div className="max-w-[15rem] 2xl:max-w-[22rem]">
          <div className="flex items-center gap-2">
            <span className="truncate font-medium">{log.event_title}</span>
            {log.trigger === 'test' && (
              <Badge variant="secondary">{t('notification.trigger_test')}</Badge>
            )}
          </div>
          {log.body && (
            <div className="truncate text-xs text-muted-foreground" title={log.body}>
              {log.body}
            </div>
          )}
          {log.error && (
            <div className="truncate text-xs text-[var(--loss)]" title={log.error}>
              {log.error}
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'targets',
      title: t('notification.log.recipients'),
      render: (log) => <RecipientsCell log={log} />,
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
      key: 'level',
      title: t('notification.level'),
      render: (log) => (
        <Badge variant={LEVEL_VARIANT[log.level]}>{t(`notification.level_${log.level}`)}</Badge>
      ),
    },
    {
      key: 'attempts',
      title: t('notification.log.attempts'),
      className: 'text-muted-foreground tabular-nums',
    },
    {
      key: 'started_at',
      title: t('notification.log.time'),
      className: 'text-xs text-muted-foreground',
      render: (log) => fmtDateTime(log.started_at),
    },
  ];

  return (
    <>
      <DataTable
        columns={columns}
        data={logs ?? []}
        loading={isLoading}
        searchable
        searchPlaceholder={t('common.search')}
        emptyMessage={t('notification.no_logs')}
        getRowKey={(log) => log.id}
        onRowClick={setSelected}
      />
      <LogDetailDialog
        log={selected}
        open={selected !== null}
        onOpenChange={(o) => !o && setSelected(null)}
      />
    </>
  );
}
