import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient, type Query } from '@tanstack/react-query';
import { syncService } from '@/services/syncService';
import type {
  GoldBackfillRequest,
  GoldSyncRequest,
  SyncJobList,
  SyncJobPage,
  SyncJobQuery,
  SyncProgressEvent,
} from '@/types/sync';
import { marketKeys } from './useMarketQuery';

/** Query-key factory — the single source of cache keys for the sync queue. */
export const syncKeys = {
  all: ['sync'] as const,
  jobs: () => [...syncKeys.all, 'jobs'] as const,
  latest: () => [...syncKeys.all, 'latest'] as const,
  page: (query: SyncJobQuery) => [...syncKeys.all, 'page', query] as const,
};

/**
 * The queue. Polls every 1.5s while any job is live (drives progress bars and
 * the pending→running→done transitions), then idles. SSE cross-process frames
 * only arrive on the `redis` coordination backend, so this poll — not the
 * stream — is what reliably advances the UI in every deployment.
 */
export function useSyncJobs() {
  return useQuery({
    queryKey: syncKeys.jobs(),
    queryFn: () => syncService.listJobs(),
    refetchInterval: (query: Query<SyncJobList>) => {
      const live = (query.state.data?.active.length ?? 0) > 0;
      return live ? 1500 : false;
    },
  });
}

/**
 * One filtered page of the queue (the Scheduler → Queue table). Separate from
 * {@link useSyncJobs}, which stays the small always-on "what is live right now"
 * read the gold panes use — this one follows the user's filters and page and
 * would be the wrong thing to answer "is a backfill queued?" with.
 *
 * Polls on `active_count`, not on what is visible: a job running on page 1 must
 * still drive the "N running" chip while the user reads page 4.
 */
export function useSyncJobPage(query: SyncJobQuery) {
  return useQuery({
    queryKey: syncKeys.page(query),
    queryFn: () => syncService.searchJobs(query),
    placeholderData: (prev) => prev, // keep the old page visible while paging
    refetchInterval: (q: Query<SyncJobPage>) =>
      (q.state.data?.active_count ?? 0) > 0 ? 1500 : false,
  });
}

/**
 * Last finished job per `job_type`, for the Jobs tab's "last run" column.
 *
 * Deliberately no `refetchInterval`: the Jobs pane already refetches on its 5s
 * `RefreshCountdown`, and this data only changes when a job finishes — a third
 * independent clock on the page would buy nothing and cost a request every
 * 1.5s. `useSyncStream` invalidates `syncKeys.all`, so a redis deployment
 * refreshes it the moment a job completes anyway.
 */
export function useLatestSyncJobs() {
  return useQuery({
    queryKey: syncKeys.latest(),
    queryFn: () => syncService.latestJobs(),
  });
}

/** The `dedup_key`s currently live — powers "disable the button if queued". */
export function useActiveSyncKeys(): Set<string> {
  const { data } = useSyncJobs();
  return new Set((data?.active ?? []).map((j) => j.dedup_key));
}

export function useEnqueueGoldBackfill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GoldBackfillRequest) => syncService.enqueueGoldBackfill(body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: syncKeys.all }),
  });
}

export function useEnqueueGoldSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GoldSyncRequest) => syncService.enqueueGoldSync(body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: syncKeys.all }),
  });
}

export function useCancelSyncJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => syncService.cancelJob(jobId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: syncKeys.all }),
  });
}

/**
 * Subscribe to `sync.progress` frames on the shared SSE stream and refresh the
 * queue (and, on completion, the gold board). Best-effort: on the `memory`
 * backend a data-plane frame never reaches this process, so the poll in
 * {@link useSyncJobs} remains the backbone — this just makes redis snappier.
 */
export function useSyncStream() {
  const qc = useQueryClient();
  useEffect(() => {
    const base = import.meta.env.VITE_API_BASE_URL || '';
    const source = new EventSource(`${base}/api/portfolios/stream`, {
      withCredentials: true,
    });

    const onMessage = (event: MessageEvent) => {
      let payload: Partial<SyncProgressEvent>;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return; // heartbeat / market-refresh / malformed — ignore
      }
      if (payload.event !== 'sync.progress') return;
      void qc.invalidateQueries({ queryKey: syncKeys.all });
      if (payload.status === 'success') {
        void qc.invalidateQueries({ queryKey: marketKeys.all });
      }
    };

    source.addEventListener('data_refreshed', onMessage as EventListener);
    return () => {
      source.removeEventListener('data_refreshed', onMessage as EventListener);
      source.close();
    };
  }, [qc]);
}
