import { type FC } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ListChecks, Loader2, XCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/hooks/useAuth';
import { useFormatDateTime } from '@/hooks/useFormatDateTime';
import { useCancelSyncJob, useSyncJobs, useSyncStream } from '@/hooks/useSyncQuery';
import { isActiveStatus, type SyncJob } from '@/types/sync';
import { SyncProgressBar, syncStatusBadge } from '@modules/market/components/SyncProgressBar';

/** Human summary of a job's params (source + range / target). */
function describeJob(job: SyncJob): string {
  const p = job.params as { source?: string; code?: string; date_from?: string; date_to?: string };
  const parts: string[] = [];
  if (p.source) parts.push(p.source + (p.code ? `:${p.code}` : ''));
  if (p.date_from && p.date_to) parts.push(`${p.date_from} → ${p.date_to}`);
  return parts.join(' · ');
}

const SyncJobRow: FC<{ job: SyncJob }> = ({ job }) => {
  const { t } = useTranslation();
  const fmtDateTime = useFormatDateTime();
  const cancel = useCancelSyncJob();
  const badge = syncStatusBadge(job.status);
  const active = isActiveStatus(job.status);

  return (
    <div className="flex flex-col gap-2 rounded-md border border-border/60 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge variant={badge.variant}>{t(badge.labelKey)}</Badge>
          <span className="text-sm font-medium">
            {t(`market.sync.job_type.${job.job_type}`, { defaultValue: job.job_type })}
          </span>
          <span className="text-xs text-muted-foreground">{describeJob(job)}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="tabular-nums text-xs text-muted-foreground">
            {job.progress_done}/{job.progress_total} · {job.progress_pct}%
          </span>
          {active && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => cancel.mutate(job.id)}
              disabled={cancel.isPending}
            >
              <XCircle className="h-4 w-4" />
              {t('market.sync.cancel')}
            </Button>
          )}
        </div>
      </div>

      <SyncProgressBar pct={Number(job.progress_pct)} muted={!active} />

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>{job.message ?? ''}</span>
        <span>{fmtDateTime(job.finished_at ?? job.started_at ?? job.create_time)}</span>
      </div>
    </div>
  );
};

/**
 * Sync Queue — the shared FIFO queue of DuckDB-write jobs (gold backfill /
 * sync-now today; stock later). Superuser-only; live jobs run one at a time and
 * can be cancelled, with recent history below. Poll + SSE keep it current.
 */
export const SyncQueuePage: FC = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { data, isLoading } = useSyncJobs();
  useSyncStream();

  if (!user?.is_superuser) return <Navigate to="/market/gold/overview" replace />;

  const active = data?.active ?? [];
  const activeIds = new Set(active.map((j) => j.id));
  const history = (data?.recent ?? []).filter((j) => !activeIds.has(j.id));

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/15 text-primary">
          <ListChecks className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{t('market.sync.queue_title')}</h1>
          <p className="text-sm text-muted-foreground">{t('market.sync.queue_subtitle')}</p>
        </div>
        <Button variant="outline" asChild>
          <Link to="/market/gold/data">
            <ArrowLeft className="h-4 w-4" />
            {t('market.sync.back_to_gold')}
          </Link>
        </Button>
      </div>

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                {active.length > 0 && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
                {t('market.sync.active')} ({active.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {active.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  {t('market.sync.no_active')}
                </p>
              ) : (
                active.map((job) => <SyncJobRow key={job.id} job={job} />)
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('market.sync.recent')}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {history.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  {t('market.sync.no_jobs')}
                </p>
              ) : (
                history.map((job) => <SyncJobRow key={job.id} job={job} />)
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};
