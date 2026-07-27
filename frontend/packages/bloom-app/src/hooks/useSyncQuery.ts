import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient, type Query } from '@tanstack/react-query';
import { syncService } from '@/services/syncService';
import type {
  GoldBackfillRequest,
  GoldSyncRequest,
  SyncJobList,
  SyncProgressEvent,
} from '@/types/sync';
import { marketKeys } from './useMarketQuery';

/** Query-key factory — the single source of cache keys for the sync queue. */
export const syncKeys = {
  all: ['sync'] as const,
  jobs: () => [...syncKeys.all, 'jobs'] as const,
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

/** The `dedup_key`s currently live — powers "disable the button if queued". */
export function useActiveSyncKeys(): Set<string> {
  const { data } = useSyncJobs();
  return new Set((data?.active ?? []).map((j) => j.dedup_key));
}

export function useEnqueueGoldBackfill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GoldBackfillRequest) => syncService.enqueueGoldBackfill(body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: syncKeys.jobs() }),
  });
}

export function useEnqueueGoldSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GoldSyncRequest) => syncService.enqueueGoldSync(body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: syncKeys.jobs() }),
  });
}

export function useCancelSyncJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => syncService.cancelJob(jobId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: syncKeys.jobs() }),
  });
}

/**
 * Subscribe to `sync.progress` frames on the shared SSE stream and refresh the
 * queue (and, on completion, the gold board). Best-effort: on the `memory`
 * backend a data-server frame never reaches this process, so the poll in
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
      void qc.invalidateQueries({ queryKey: syncKeys.jobs() });
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
