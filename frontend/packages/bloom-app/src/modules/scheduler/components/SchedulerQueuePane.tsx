import { type FC, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DataTable,
  type DataTableColumn,
  type DataTableFilterChip,
} from '@/components/ui/data-table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useFormatDateTime } from '@/hooks/useFormatDateTime';
import { useCancelSyncJob, useSyncJobs, useSyncStream } from '@/hooks/useSyncQuery';
import { isActiveStatus, type SyncJob } from '@/types/sync';
import { SyncProgressBar, syncStatusBadge } from '@modules/market/components/SyncProgressBar';
import { RefreshCountdown } from './RefreshCountdown';

type StatusFilter = 'active' | 'all';
type TypeFilter = 'all' | 'gold' | 'stock' | 'coin';
type SourceFilter = 'all' | 'yahoo' | 'sjc' | 'mihong';

const TYPE_OPTIONS: TypeFilter[] = ['all', 'gold', 'stock', 'coin'];
const SOURCE_OPTIONS: SourceFilter[] = ['all', 'yahoo', 'sjc', 'mihong'];

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
 * Queue tab — the shared FIFO `sync_jobs` queue as a filterable dataview.
 * Active + recent are merged and de-duped by id, filtered by status / type /
 * source, then sorted by `create_time` ascending (FIFO). Defaults to the
 * active (pending/running) jobs. A live job can be cancelled inline.
 *
 * Note: the endpoint returns all `active` jobs but only the 50 most-recent
 * others, so history filtering is bounded to that window (client-side).
 */
export const SchedulerQueuePane: FC = () => {
  const { t } = useTranslation();
  const fmtDateTime = useFormatDateTime();
  const { data, isLoading, isFetching, refetch } = useSyncJobs();
  const cancel = useCancelSyncJob();
  useSyncStream();

  const [status, setStatus] = useState<StatusFilter>('active');
  const [type, setType] = useState<TypeFilter>('all');
  const [source, setSource] = useState<SourceFilter>('all');

  // Merge active + recent, de-dupe by id (active wins — it is the freshest copy
  // of a row that also appears in recent).
  const merged = useMemo(() => {
    const byId = new Map<string, SyncJob>();
    for (const j of data?.recent ?? []) byId.set(j.id, j);
    for (const j of data?.active ?? []) byId.set(j.id, j);
    return [...byId.values()];
  }, [data]);

  const filtered = useMemo(() => {
    const rows = merged.filter((j) => {
      if (status === 'active' && !isActiveStatus(j.status)) return false;
      if (type !== 'all' && jobType(j) !== type) return false;
      if (source !== 'all' && jobSource(j) !== source) return false;
      return true;
    });
    // DataTable does not sort by default — pre-sort FIFO (create_time asc).
    return rows.sort((a, b) => (a.create_time ?? '').localeCompare(b.create_time ?? ''));
  }, [merged, status, type, source]);

  const chips: DataTableFilterChip[] = [];
  if (status === 'active') {
    chips.push({
      id: 'status',
      label: `${t('market.sync.filter_status')}: ${t('market.sync.status_active')}`,
      onRemove: () => setStatus('all'),
    });
  }
  if (type !== 'all') {
    chips.push({
      id: 'type',
      label: `${t('market.sync.filter_type')}: ${t(`market.sync.type.${type}`)}`,
      onRemove: () => setType('all'),
    });
  }
  if (source !== 'all') {
    chips.push({
      id: 'source',
      label: `${t('market.sync.filter_source')}: ${t(`market.sync.source.${source}`)}`,
      onRemove: () => setSource('all'),
    });
  }

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
      key: 'time',
      title: t('market.sync.col_time'),
      className: 'tabular-nums',
      sortable: true,
      sortAccessor: (j) => j.finished_at ?? j.started_at ?? j.create_time ?? '',
      render: (j) => fmtDateTime(j.finished_at ?? j.started_at ?? j.create_time),
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
            className="h-7 gap-1.5"
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Select value={status} onValueChange={(v) => setStatus(v as StatusFilter)}>
            <SelectTrigger className="h-9 w-[9rem]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="active">{t('market.sync.status_active')}</SelectItem>
              <SelectItem value="all">{t('market.sync.all')}</SelectItem>
            </SelectContent>
          </Select>
          <Select value={type} onValueChange={(v) => setType(v as TypeFilter)}>
            <SelectTrigger className="h-9 w-[9rem]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TYPE_OPTIONS.map((o) => (
                <SelectItem key={o} value={o}>
                  {o === 'all' ? t('market.sync.all') : t(`market.sync.type.${o}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={source} onValueChange={(v) => setSource(v as SourceFilter)}>
            <SelectTrigger className="h-9 w-[10rem]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SOURCE_OPTIONS.map((o) => (
                <SelectItem key={o} value={o}>
                  {o === 'all' ? t('market.sync.all') : t(`market.sync.source.${o}`)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <RefreshCountdown onRefresh={() => void refetch()} refreshing={isFetching} />
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        loading={isLoading}
        pageSize={50}
        searchable={false}
        enableExport
        exportFilename="sync-queue.csv"
        getRowKey={(j) => j.id}
        filterChips={chips}
        emptyMessage={t('market.sync.no_jobs')}
      />
    </div>
  );
};
