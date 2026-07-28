import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { Ban, Play } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useFormatDateTime } from '@/hooks/useFormatDateTime';
import { useCrawlStatus } from '@/hooks/useSchedulerQuery';
import type { CrawlJob } from '@/types/scheduler';
import { RefreshCountdown } from './RefreshCountdown';

/** Run / Cancel placeholders — rendered but disabled, with a "TBD" hint. The
 * disabled button can't fire hover events, so the trigger wraps it in a span. */
const JobActions: FC = () => {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-end gap-1">
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0} className="inline-flex">
            <Button size="sm" variant="ghost" disabled>
              <Play className="h-3.5 w-3.5" />
              {t('scheduler.jobs.run')}
            </Button>
          </span>
        </TooltipTrigger>
        <TooltipContent>{t('scheduler.jobs.tbd')}</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0} className="inline-flex">
            <Button size="sm" variant="ghost" disabled>
              <Ban className="h-3.5 w-3.5" />
              {t('scheduler.jobs.cancel')}
            </Button>
          </span>
        </TooltipTrigger>
        <TooltipContent>{t('scheduler.jobs.tbd')}</TooltipContent>
      </Tooltip>
    </div>
  );
};

/**
 * Jobs tab — the recurring APScheduler cron jobs (read-only). Header shows the
 * scheduler run-state + vnstock tier and a 5s refresh countdown; the table
 * lists each job's cadence and next fire time. Run/Cancel are placeholders.
 */
export const SchedulerJobsPane: FC = () => {
  const { t } = useTranslation();
  const fmtDateTime = useFormatDateTime();
  const { data, isLoading, isFetching, refetch } = useCrawlStatus();
  const jobs = data?.jobs ?? [];

  const columns: DataTableColumn<CrawlJob>[] = [
    {
      key: 'name',
      title: t('scheduler.jobs.col_job'),
      sortable: true,
      sortAccessor: (r) => r.name ?? r.id,
      render: (r) => <span className="font-medium">{r.name ?? r.id}</span>,
    },
    {
      key: 'id',
      title: t('scheduler.jobs.col_id'),
      className: 'text-muted-foreground',
      render: (r) => r.id,
    },
    {
      key: 'cadence',
      title: t('scheduler.jobs.col_cadence'),
      render: (r) => <span className="text-xs text-muted-foreground">{r.cadence ?? '—'}</span>,
    },
    {
      key: 'next_run_time',
      title: t('scheduler.jobs.col_next'),
      className: 'tabular-nums',
      sortable: true,
      sortAccessor: (r) => r.next_run_time ?? '',
      render: (r) => fmtDateTime(r.next_run_time),
    },
    {
      key: 'status',
      title: t('scheduler.jobs.col_status'),
      render: (r) =>
        r.paused ? (
          <Badge variant="outline">{t('scheduler.jobs.paused')}</Badge>
        ) : (
          <Badge variant="success">{t('scheduler.jobs.scheduled')}</Badge>
        ),
    },
    {
      key: 'actions',
      title: '',
      hideable: false,
      align: 'right',
      render: () => <JobActions />,
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={data?.scheduler_running ? 'success' : 'outline'}>
            {data?.scheduler_running ? t('scheduler.jobs.running') : t('scheduler.jobs.stopped')}
          </Badge>
          {data?.vnstock_tier && (
            <Badge variant="secondary">
              {t('scheduler.jobs.tier', { tier: data.vnstock_tier })}
            </Badge>
          )}
        </div>
        <RefreshCountdown onRefresh={() => void refetch()} refreshing={isFetching} />
      </div>

      <DataTable
        columns={columns}
        data={jobs}
        loading={isLoading}
        pageSize={50}
        searchable={false}
        getRowKey={(r) => r.id}
        emptyMessage={t('scheduler.jobs.empty')}
      />
    </div>
  );
};
