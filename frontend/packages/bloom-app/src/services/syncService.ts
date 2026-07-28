import { apiClient } from './apiClient';
import type { ApiResponse } from '@/types/api';
import type {
  EnqueueSyncJobResponse,
  GoldBackfillRequest,
  GoldSyncRequest,
  SyncJob,
  SyncJobList,
  SyncJobPage,
  SyncJobQuery,
} from '@/types/sync';

/** Sync-job queue — superuser gold backfill / sync-now + queue management.
 *
 * Enqueue is a plain Postgres insert on the control plane (not a data-plane
 * forward); the single data-plane dispatcher later claims and runs the row. */
export const syncService = {
  enqueueGoldBackfill: async (body: GoldBackfillRequest): Promise<EnqueueSyncJobResponse> => {
    const { data } = await apiClient.post<ApiResponse<EnqueueSyncJobResponse>>(
      '/api/market/gold/backfill',
      body,
    );
    return data.data;
  },

  enqueueGoldSync: async (body: GoldSyncRequest = {}): Promise<EnqueueSyncJobResponse> => {
    const { data } = await apiClient.post<ApiResponse<EnqueueSyncJobResponse>>(
      '/api/market/gold/sync',
      body,
    );
    return data.data;
  },

  listJobs: async (limit = 50): Promise<SyncJobList> => {
    const { data } = await apiClient.get<ApiResponse<SyncJobList>>('/api/market/sync/jobs', {
      params: { limit },
    });
    return data.data;
  },

  /** One filtered, ordered page of the whole queue — filtering and paging both
   *  happen in SQL, so a narrow filter searches every row, not a recent window. */
  searchJobs: async (query: SyncJobQuery = {}): Promise<SyncJobPage> => {
    const { data } = await apiClient.get<ApiResponse<SyncJobPage>>('/api/market/sync/jobs/search', {
      params: query,
    });
    return data.data;
  },

  cancelJob: async (jobId: string): Promise<SyncJob> => {
    const { data } = await apiClient.post<ApiResponse<SyncJob>>(
      `/api/market/sync/jobs/${jobId}/cancel`,
    );
    return data.data;
  },
};
