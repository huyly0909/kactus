import { useQuery } from '@tanstack/react-query';
import { crawlService } from '@/services/crawlService';

/** Query-key factory for the scheduler status. */
export const crawlKeys = {
  all: ['crawl'] as const,
  status: () => [...crawlKeys.all, 'status'] as const,
};

/**
 * Scheduler status (cron jobs + vnstock tier). Fetched once on mount; there is
 * no `refetchInterval` — the Scheduler page's `RefreshCountdown` owns the
 * cadence and calls `refetch()` on each tick / manual click.
 */
export function useCrawlStatus() {
  return useQuery({
    queryKey: crawlKeys.status(),
    queryFn: () => crawlService.crawlStatus(),
  });
}
