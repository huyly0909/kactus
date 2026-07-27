import { apiClient } from './apiClient';
import type { ApiResponse } from '@/types/api';
import type { CrawlStatus } from '@/types/scheduler';

/** Crawl-scheduler service — read-only status of the data-plane cron jobs
 * (superuser). The control plane forwards this from the data plane. */
export const crawlService = {
  crawlStatus: async (): Promise<CrawlStatus> => {
    const { data } = await apiClient.get<ApiResponse<CrawlStatus>>(
      '/api/admin/portfolios/crawl-status',
    );
    return data.data;
  },
};
