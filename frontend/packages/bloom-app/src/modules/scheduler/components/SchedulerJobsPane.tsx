import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Ban, Play } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useFormatDateTime } from '@/hooks/useFormatDateTime';
import { useCrawlStatus } from '@/hooks/useSchedulerQuery';
import { useLatestSyncJobs, useSyncJobs } from '@/hooks/useSyncQuery';
import { cn } from '@/lib/utils';
import type { CrawlJob } from '@/types/scheduler';
import type { SyncJob } from '@/types/sync';
import { syncStatusBadge } from '@modules/market/components/SyncProgressBar';
import { describeCadence } from './cadence';
import { RefreshCountdown } from './RefreshCountdown';

/** Which queue `job_type`s a cron job enqueues — mirrors
 * `kactus_common.portfolio.crawl_queue` (`{asset}_{kind}`). Quotes fans out to
 * both asset families; everything else is stock-only or the catalog. */
const JOB_TYPES_BY_SCHEDULER_ID: Record<string, string[]> = {
  crawl_quotes: ['stock_quotes', 'gold_quotes'],
  crawl_news: ['stock_news'],
  crawl_ratios: ['stock_ratios'],
  crawl_events: ['stock_events'],
  crawl_ohlcv: ['stock_ohlcv'],
  sync_catalog: ['catalog_sync'],
};

/** Worst-first, so a cron job that fans out to two queue types reports the bad
 * half. A green "success" beside a silently failing gold crawl is the exact
 * lie this column exists to prevent. */
const STATUS_SEVERITY: Record<string, number> = { failed: 3, cancelled: 2, success: 1 };

/** The run to report for a cron job: of the queue types it enqueues, the worst
 * outcome, ties broken by recency. Undefined when none has ever finished. */
function lastRunFor(schedulerId: string, latest: Map<string, SyncJob>): SyncJob | undefined {
  const runs = (JOB_TYPES_BY_SCHEDULER_ID[schedulerId] ?? [])
    .map((jt) => latest.get(jt))
    .filter((j): j is SyncJob => !!j);
  return runs.sort((a, b) => {
    const sev = (STATUS_SEVERITY[b.status] ?? 0) - (STATUS_SEVERITY[a.status] ?? 0);
    return sev !== 0 ? sev : (b.finished_at ?? '').localeCompare(a.finished_at ?? '');
  })[0];
}

/** "in 18h" / "in 12m" — the answer to "is this about to fire?", which an
 * absolute stamp makes you compute yourself. Past due reads as "now". */
function relativeTo(iso: string | null | undefined): { key: string; value: string } | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(ms)) return null;
  if (ms <= 0) return { key: 'scheduler.jobs.next_due', value: '' };
  const mins = Math.round(ms / 60000);
  if (mins < 60) return { key: 'scheduler.jobs.next_in_min', value: String(mins) };
  const hours = Math.round(mins / 60);
  if (hours < 24) return { key: 'scheduler.jobs.next_in_hour', value: String(hours) };
  return { key: 'scheduler.jobs.next_in_day', value: String(Math.round(hours / 24)) };
}

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
  const navigate = useNavigate();
  const { data, isLoading, isFetching, refetch } = useCrawlStatus();
  const jobs = data?.jobs ?? [];
  const { data: queue } = useSyncJobs();
  const { data: latestJobs } = useLatestSyncJobs();

  const latestByType = new Map((latestJobs ?? []).map((j) => [j.job_type, j]));

  // Live queue tally per job_type — the active list is small (live jobs only),
  // so counting client-side per render is cheap.
  const liveByType = new Map<string, { pending: number; running: number }>();
  for (const j of queue?.active ?? []) {
    const entry = liveByType.get(j.job_type) ?? { pending: 0, running: 0 };
    if (j.status === 'running') entry.running += 1;
    else entry.pending += 1;
    liveByType.set(j.job_type, entry);
  }

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
      defaultHidden: true,
      render: (r) => r.id,
    },
    {
      // The raw `cron[...]` string is a Python repr; phrase it instead, and keep
      // the repr in the tooltip for whoever is actually debugging the trigger.
      key: 'cadence',
      title: t('scheduler.jobs.col_cadence'),
      render: (r) => {
        const parts = describeCadence(r.cron, r.timezone);
        if (!parts)
          return <span className="text-xs text-muted-foreground">{r.cadence ?? '—'}</span>;
        const days = parts.values.days;
        return (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="text-xs">
                {t(parts.key, {
                  ...parts.values,
                  ...(days
                    ? { days: t(`scheduler.cadence.dow.${days}`, { defaultValue: days }) }
                    : {}),
                })}
              </span>
            </TooltipTrigger>
            <TooltipContent className="font-mono text-xs">{r.cadence}</TooltipContent>
          </Tooltip>
        );
      },
    },
    {
      key: 'next_run_time',
      title: t('scheduler.jobs.col_next'),
      className: 'tabular-nums',
      sortable: true,
      sortAccessor: (r) => r.next_run_time ?? '',
      render: (r) => {
        const rel = relativeTo(r.next_run_time);
        return (
          <div className="leading-tight">
            <div>{fmtDateTime(r.next_run_time)}</div>
            {rel && (
              <div className="text-xs text-muted-foreground">{t(rel.key, { n: rel.value })}</div>
            )}
          </div>
        );
      },
    },
    {
      // What the Jobs tab could not answer before: did the last fire work?
      key: 'last_run',
      title: t('scheduler.jobs.col_last_run'),
      render: (r) => {
        const run = lastRunFor(r.id, latestByType);
        if (!run) return <span className="text-xs text-muted-foreground">—</span>;
        const badge = syncStatusBadge(run.status);
        // `result` is an untyped handler payload; only render `rows` when the
        // handler actually reported a count.
        const rows = run.result?.rows;
        const rowText = typeof rows === 'number' ? `${rows} ${t('scheduler.jobs.rows')} · ` : '';
        const body = (
          <div className="flex flex-col items-start gap-1 leading-tight">
            <Badge variant={badge.variant}>{t(badge.labelKey)}</Badge>
            <span className="text-xs text-muted-foreground tabular-nums">
              {rowText}
              {fmtDateTime(run.finished_at)}
            </span>
          </div>
        );
        // Only a failure has something more to say — and it is the whole reason
        // the column exists, so it must not be truncated into the cell.
        return run.message ? (
          <Tooltip>
            <TooltipTrigger asChild>{body}</TooltipTrigger>
            <TooltipContent className="max-w-md">{run.message}</TooltipContent>
          </Tooltip>
        ) : (
          body
        );
      },
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
      // One chip per queue job_type this cron enqueues; a live count pulses on
      // it. Clicking lands on the Queue tab pre-filtered to that job's tasks.
      key: 'queue',
      title: t('scheduler.jobs.col_queue'),
      render: (r) => {
        const types = JOB_TYPES_BY_SCHEDULER_ID[r.id];
        if (!types) return <span className="text-xs text-muted-foreground">—</span>;
        return (
          <div className="flex flex-wrap items-center gap-1">
            {types.map((jt) => {
              const live = liveByType.get(jt);
              const liveCount = (live?.pending ?? 0) + (live?.running ?? 0);
              return (
                <Tooltip key={jt}>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      onClick={() => navigate(`/scheduler/queue?queue_job=${jt}`)}
                      className={cn(
                        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs',
                        'transition-colors hover:bg-accent hover:text-accent-foreground',
                        liveCount > 0 ? 'border-emerald-500/50' : 'border-border',
                      )}
                    >
                      {liveCount > 0 && (
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
                      )}
                      {t(`market.sync.job_type.${jt}`, { defaultValue: jt })}
                      {liveCount > 0 && <span className="tabular-nums">{liveCount}</span>}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {t('scheduler.jobs.queue_tip', {
                      pending: live?.pending ?? 0,
                      running: live?.running ?? 0,
                    })}
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </div>
        );
      },
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
        // `id` ships hidden (it only matters when debugging a trigger); the
        // column menu is what makes that reversible rather than a loss.
        enableColumnVisibility
        getRowKey={(r) => r.id}
        emptyMessage={t('scheduler.jobs.empty')}
      />
    </div>
  );
};
