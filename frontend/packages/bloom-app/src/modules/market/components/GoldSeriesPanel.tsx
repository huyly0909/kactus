import { type FC, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  AlertTriangle,
  DownloadCloud,
  LineChart,
  Loader2,
  RefreshCw,
  Table as TableIcon,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { DateRangeControl, datePresets, type DateRange } from '@/components/ui/date-range-picker';
import { useGoldHistory, useGoldSchedule } from '@/hooks/useMarketQuery';
import { useEnqueueGoldSync, useSyncJobs } from '@/hooks/useSyncQuery';
import type { GoldHistoryParams } from '@/services/marketService';
import { UNIT_USD_PER_OZ } from '@/types/market';
import { dedupKeyTouchesSource, resolveGoldBackfillMin, type GoldSource } from '@/types/sync';
import { GoldBackfillDialog } from './GoldBackfillDialog';
import { GoldHistoryChart } from './GoldHistoryChart';
import { GoldHistoryTable } from './GoldHistoryTable';
import { detectGaps, todayInTz, todayMissing } from './goldGaps';
import { SyncProgressBar, syncStatusBadge } from './SyncProgressBar';

const PANEL_PRESETS = datePresets('30d', '90d', '1y', '3y', '5y', 'all');
const defaultRange = (): DateRange => datePresets('1y')[0]?.range() ?? { from: '', to: '' };

const DAY_MS = 86_400_000;
function rangeLimit(r: DateRange): number {
  if (!r.from) return 10_000;
  const from = new Date(r.from).getTime();
  const to = (r.to ? new Date(r.to) : new Date()).getTime();
  const days = Math.max(1, Math.round((to - from) / DAY_MS));
  return Math.min(10_000, days + 60);
}

interface GoldSeriesPanelProps {
  /** History series code to chart (e.g. `SJC`, `XAU`, `999`). */
  code: string;
  /** The backfill/sync source this panel drives. */
  source: GoldSource;
  /** Code override passed to backfill (Mihong `999`); omit for SJC/Yahoo. */
  backfillCode?: string;
  /** `VND/luong` or `USD/oz` — labels the axis unit. */
  unit: string;
}

/**
 * One gold source's Data-tab panel: its history chart plus the backfill /
 * sync-now controls. While any job touching this source is live (single DuckDB
 * writer), both buttons disable and a progress bar tracks the running job.
 */
export const GoldSeriesPanel: FC<GoldSeriesPanelProps> = ({ code, source, backfillCode, unit }) => {
  const { t } = useTranslation();
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const [backfillOpen, setBackfillOpen] = useState(false);
  const enqueueSync = useEnqueueGoldSync();
  const { data: jobs } = useSyncJobs();
  const min = useMemo(() => resolveGoldBackfillMin(source), [source]);

  const params: GoldHistoryParams = {
    start: range.from || undefined,
    end: range.to || undefined,
    limit: rangeLimit(range),
  };
  const { data: points, isLoading } = useGoldHistory(code, params);

  // One history endpoint can return two series sharing a code (SJC `999` vs
  // Mihong `999`); keep only this panel's source so chart, table and the
  // gap/today chips all agree on the same rows.
  const rows = useMemo(() => (points ?? []).filter((p) => p.source === source), [points, source]);

  // Data-availability schedule (expected weekdays + holidays + market timezone)
  // drives the warning chips. `entity_id` is `source:code`; Mihong passes `999`.
  const { data: schedule } = useGoldSchedule(source, backfillCode ?? code);
  const gaps = useMemo(
    () => (schedule?.enabled ? detectGaps(rows, range.from, range.to, schedule) : []),
    [rows, range.from, range.to, schedule],
  );
  const showTodayMissing = useMemo(() => {
    if (!schedule?.enabled) return false;
    // Only meaningful when the window still reaches today.
    if (range.to && range.to < todayInTz(schedule.timezone)) return false;
    return todayMissing(rows, schedule);
  }, [rows, schedule, range.to]);

  // The live job (if any) whose work touches this source — powers the bar + the
  // disabled state. An `all` sync counts, since it writes this source too.
  const activeJob = (jobs?.active ?? []).find((j) => dedupKeyTouchesSource(j.dedup_key, source));
  const busy = Boolean(activeJob);

  const syncNow = async () => {
    try {
      const res = await enqueueSync.mutateAsync({ source });
      toast.success(res.created ? t('market.sync.queued') : t('market.sync.already_queued'));
    } catch {
      toast.error(t('market.sync.enqueue_failed'));
    }
  };

  const statusBadge = activeJob ? syncStatusBadge(activeJob.status) : null;

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2">
          <CardTitle className="text-base">{code}</CardTitle>
          <Badge variant="outline" className="text-xs">
            {unit === UNIT_USD_PER_OZ
              ? t('market.gold.unit_usd_oz')
              : t('market.gold.unit_vnd_luong')}
          </Badge>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => setBackfillOpen(true)} disabled={busy}>
            <DownloadCloud className="h-4 w-4" />
            {t('market.sync.backfill')}
          </Button>
          <Button size="sm" onClick={syncNow} disabled={busy || enqueueSync.isPending}>
            {enqueueSync.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {t('market.sync.sync_now')}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col gap-3">
        {activeJob && statusBadge && (
          <div className="flex flex-col gap-1.5 rounded-md border border-border/60 bg-muted/30 p-3">
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-2">
                <Badge variant={statusBadge.variant}>{t(statusBadge.labelKey)}</Badge>
                <span className="text-muted-foreground">
                  {t(`market.sync.job_type.${activeJob.job_type}`)}
                </span>
              </span>
              <span className="tabular-nums text-muted-foreground">
                {activeJob.progress_done}/{activeJob.progress_total} · {activeJob.progress_pct}%
              </span>
            </div>
            <SyncProgressBar pct={Number(activeJob.progress_pct)} />
          </div>
        )}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="inline-flex rounded-md border border-border p-0.5">
            <Button
              size="sm"
              variant={view === 'chart' ? 'secondary' : 'ghost'}
              onClick={() => setView('chart')}
            >
              <LineChart className="h-4 w-4" />
              {t('market.gold.view_chart')}
            </Button>
            <Button
              size="sm"
              variant={view === 'table' ? 'secondary' : 'ghost'}
              onClick={() => setView('table')}
            >
              <TableIcon className="h-4 w-4" />
              {t('market.gold.view_table')}
            </Button>
          </div>
          <DateRangeControl
            value={range}
            onChange={setRange}
            presets={PANEL_PRESETS}
            placeholder={t('common.range_custom')}
            minDate={min}
          />
        </div>

        {(gaps.length > 0 || showTodayMissing) && (
          <div className="flex flex-wrap items-center gap-2">
            {gaps.length > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="warning" className="cursor-help gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    {t('market.gold.gap_warning', { count: gaps.length })}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  <p className="font-medium">{t('market.gold.gap_tooltip_title')}</p>
                  <p className="text-muted-foreground">
                    {t('market.gold.gap_tooltip_range', {
                      from: gaps[0],
                      to: gaps[gaps.length - 1],
                    })}
                  </p>
                  <p className="mt-1 tabular-nums">
                    {gaps.slice(0, 12).join(', ')}
                    {gaps.length > 12 ? ' …' : ''}
                  </p>
                </TooltipContent>
              </Tooltip>
            )}
            {showTodayMissing && (
              <Badge variant="warning" className="gap-1">
                <AlertTriangle className="h-3 w-3" />
                {t('market.gold.today_missing')}
              </Badge>
            )}
          </div>
        )}

        {isLoading ? (
          <Skeleton className="h-[300px] w-full" />
        ) : rows.length === 0 ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            {t('market.sync.series_empty')}
          </p>
        ) : view === 'chart' ? (
          <GoldHistoryChart points={rows} unit={unit} />
        ) : (
          <GoldHistoryTable points={rows} unit={unit} />
        )}
      </CardContent>

      <GoldBackfillDialog
        source={source}
        code={backfillCode}
        open={backfillOpen}
        onOpenChange={setBackfillOpen}
      />
    </Card>
  );
};
