import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import {
  DataTableFilterBar,
  EMPTY_RANGE,
  type TableFilterDef,
} from '@/components/ui/data-table-filters';
import { datePresets, type DateRange } from '@/components/ui/date-range-picker';
import { useFormatDateTime } from '@/hooks/useFormatDateTime';
import { useTableQueryState } from '@/hooks/useTableQueryState';
import { useCancelSyncJob, useSyncJobPage, useSyncStream } from '@/hooks/useSyncQuery';
import { cn } from '@/lib/utils';
import { isActiveStatus, type SyncJob, type SyncJobQuery } from '@/types/sync';
import { SyncProgressBar, syncStatusBadge } from '@modules/market/components/SyncProgressBar';
import { RefreshCountdown } from './RefreshCountdown';

const PAGE_SIZE = 20;
const STATUS_OPTIONS = [
  'all',
  'active',
  'pending',
  'running',
  'success',
  'failed',
  'cancelled',
] as const;
const TYPE_OPTIONS = ['all', 'gold', 'stock', 'coin'] as const;
const SOURCE_OPTIONS = ['all', 'yahoo', 'sjc', 'mihong'] as const;

/** Asset family — the first segment of `job_type` (`gold_backfill` → `gold`). */
function jobType(job: SyncJob): string {
  return job.job_type.split('_')[0] ?? '';
}

/** Source the job touches, from its params (gold jobs carry `source`). */
function jobSource(job: SyncJob): string {
  const p = job.params as { source?: string };
  return p.source ?? '';
}

/** Human summary of a job's params (source + range / target). */
function describeJob(job: SyncJob): string {
  const p = job.params as { source?: string; code?: string; date_from?: string; date_to?: string };
  const parts: string[] = [];
  if (p.source) parts.push(p.source + (p.code ? `:${p.code}` : ''));
  if (p.date_from && p.date_to) parts.push(`${p.date_from} → ${p.date_to}`);
  return parts.join(' · ');
}

/**
 * Queue tab — the shared `sync_jobs` queue, newest first.
 *
 * Filtering, ordering and paging all happen in SQL: a narrow filter searches
 * every row rather than a recent window, and the page state lives in the URL so
 * a filtered view survives a reload. `active_count` comes back with every page
 * and is global, so the "N running" chip stays truthful on page 4 of the
 * finished history. A live job can be cancelled inline.
 *
 * Note: CSV export covers the **current page** — `DataTable` exports the rows
 * it was handed, and the whole point here is that it is no longer handed the
 * whole table.
 */
export const SchedulerQueuePane: FC = () => {
  const { t } = useTranslation();
  const fmtDateTime = useFormatDateTime();
  const cancel = useCancelSyncJob();
  useSyncStream();

  const { page, setPage, pageSize, sort, setSort, filters, setFilter } = useTableQueryState({
    defaultFilters: {
      status: 'all',
      type: 'all',
      source: 'all',
      created: EMPTY_RANGE as DateRange,
    },
    defaultSort: { key: 'create_time', desc: true },
    pageSize: PAGE_SIZE,
    urlKey: 'queue',
  });

  const created = filters.created as DateRange;
  const query: SyncJobQuery = {
    page,
    page_size: pageSize,
    order: sort?.desc === false ? 'asc' : 'desc',
    ...(filters.status !== 'all' && { status: filters.status as SyncJobQuery['status'] }),
    ...(filters.type !== 'all' && { type: filters.type as string }),
    ...(filters.source !== 'all' && { source: filters.source as string }),
    ...(created.from && { created_from: created.from }),
    ...(created.to && { created_to: created.to }),
  };
  const { data, isLoading, isFetching, refetch } = useSyncJobPage(query);

  const filterDefs: TableFilterDef[] = [
    {
      id: 'status',
      kind: 'select',
      label: t('market.sync.filter_status'),
      options: STATUS_OPTIONS.map((o) => ({
        value: o,
        label:
          o === 'all'
            ? t('market.sync.all')
            : o === 'active'
              ? t('market.sync.status_active')
              : t(`market.sync.status.${o}`),
      })),
    },
    {
      id: 'type',
      kind: 'select',
      label: t('market.sync.filter_type'),
      options: TYPE_OPTIONS.map((o) => ({
        value: o,
        label: o === 'all' ? t('market.sync.all') : t(`market.sync.type.${o}`),
      })),
    },
    {
      id: 'source',
      kind: 'select',
      label: t('market.sync.filter_source'),
      options: SOURCE_OPTIONS.map((o) => ({
        value: o,
        label: o === 'all' ? t('market.sync.all') : t(`market.sync.source.${o}`),
      })),
    },
    {
      id: 'created',
      kind: 'dateRange',
      label: t('market.sync.filter_created'),
      presets: datePresets('today', 'yesterday', '7d', '30d', '90d', 'month', 'all'),
    },
  ];

  const activeCount = data?.active_count ?? 0;

  const columns: DataTableColumn<SyncJob>[] = [
    {
      key: 'status',
      title: t('market.sync.col_status'),
      render: (j) => {
        const badge = syncStatusBadge(j.status);
        return <Badge variant={badge.variant}>{t(badge.labelKey)}</Badge>;
      },
    },
    {
      key: 'type',
      title: t('market.sync.col_type'),
      render: (j) => t(`market.sync.type.${jobType(j)}`, { defaultValue: jobType(j) }),
    },
    {
      key: 'source',
      title: t('market.sync.col_source'),
      render: (j) => t(`market.sync.source.${jobSource(j)}`, { defaultValue: jobSource(j) || '—' }),
    },
    {
      key: 'job',
      title: t('market.sync.col_job'),
      render: (j) => (
        <div className="flex flex-col">
          <span className="text-sm font-medium">
            {t(`market.sync.job_type.${j.job_type}`, { defaultValue: j.job_type })}
          </span>
          <span className="text-xs text-muted-foreground">{describeJob(j)}</span>
        </div>
      ),
    },
    {
      key: 'progress',
      title: t('market.sync.col_progress'),
      className: 'min-w-[9rem]',
      render: (j) => (
        <div className="flex flex-col gap-1">
          <span className="tabular-nums text-xs text-muted-foreground">
            {j.progress_done}/{j.progress_total} · {j.progress_pct}%
          </span>
          <SyncProgressBar pct={Number(j.progress_pct)} muted={!isActiveStatus(j.status)} />
        </div>
      ),
    },
    {
      // Sorted server-side on `create_time` — so that is what the cell leads
      // with. The finished stamp rides along underneath rather than in front,
      // where it would silently disagree with the ordering.
      key: 'create_time',
      title: t('market.sync.col_queued'),
      className: 'tabular-nums',
      sortable: true,
      exportValue: (j) => j.create_time ?? '',
      render: (j) => (
        <div className="flex flex-col">
          <span className="whitespace-nowrap">{fmtDateTime(j.create_time)}</span>
          {j.finished_at && (
            <span className="whitespace-nowrap text-xs text-muted-foreground">
              {t('market.sync.finished_at', { time: fmtDateTime(j.finished_at) })}
            </span>
          )}
        </div>
      ),
    },
    {
      key: 'actions',
      title: '',
      hideable: false,
      align: 'right',
      render: (j) =>
        isActiveStatus(j.status) ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => cancel.mutate(j.id)}
            disabled={cancel.isPending}
          >
            <XCircle className="h-3.5 w-3.5" />
            {t('market.sync.cancel')}
          </Button>
        ) : null,
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <DataTableFilterBar
        filters={filterDefs}
        values={filters}
        onChange={setFilter}
        actions={
          <>
            <Button
              size="sm"
              variant={filters.status === 'active' ? 'default' : 'outline'}
              disabled={activeCount === 0}
              onClick={() => setFilter('status', 'active')}
              className="gap-1.5"
            >
              <span
                className={cn(
                  'h-2 w-2 rounded-full',
                  activeCount > 0 ? 'animate-pulse bg-emerald-500' : 'bg-muted-foreground/40',
                )}
              />
              {t('market.sync.active_count', { count: activeCount })}
            </Button>
            <RefreshCountdown onRefresh={() => void refetch()} refreshing={isFetching} />
          </>
        }
      />

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isLoading}
        searchable={false}
        enableExport
        exportFilename="sync-queue.csv"
        getRowKey={(j) => j.id}
        sort={sort}
        onSortChange={setSort}
        pagination={{
          mode: 'server',
          page,
          pageSize,
          total: data?.total ?? 0,
          onPageChange: setPage,
        }}
        emptyMessage={t('market.sync.no_jobs')}
      />
    </div>
  );
};
