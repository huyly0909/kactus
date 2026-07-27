import { type FC, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { DownloadCloud, Loader2, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { DateRangeControl, datePresets, type DateRange } from '@/components/ui/date-range-picker';
import { useGoldHistory } from '@/hooks/useMarketQuery';
import { useEnqueueGoldSync, useSyncJobs } from '@/hooks/useSyncQuery';
import type { GoldHistoryParams } from '@/services/marketService';
import { UNIT_USD_PER_OZ } from '@/types/market';
import { dedupKeyTouchesSource, resolveGoldBackfillMin, type GoldSource } from '@/types/sync';
import { GoldBackfillDialog } from './GoldBackfillDialog';
import { GoldHistoryChart } from './GoldHistoryChart';
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

        <div className="flex justify-end">
          <DateRangeControl
            value={range}
            onChange={setRange}
            presets={PANEL_PRESETS}
            placeholder={t('common.range_custom')}
            minDate={min}
          />
        </div>

        {isLoading ? (
          <Skeleton className="h-[300px] w-full" />
        ) : (points ?? []).length === 0 ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            {t('market.sync.series_empty')}
          </p>
        ) : (
          <GoldHistoryChart points={points ?? []} unit={unit} />
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
