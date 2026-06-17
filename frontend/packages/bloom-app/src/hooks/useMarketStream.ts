import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { portfolioKeys } from './usePortfolioQuery';
import type { MarketRefreshedEvent } from '@/types/portfolio';

/** Subscribe to the in-app SSE stream and refetch market data on each nudge.
 *
 * The backend broadcasts a `data_refreshed` event to ALL subscribers whenever a
 * crawl writes fresh data; we invalidate the portfolio caches so any visible
 * quotes/news widget refetches.  EventSource auto-reconnects on transient drops.
 */
export function useMarketStream(options: { notify?: boolean } = {}) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const notify = options.notify ?? false;

  useEffect(() => {
    const base = import.meta.env.VITE_API_BASE_URL || '';
    const source = new EventSource(`${base}/api/portfolios/stream`, {
      withCredentials: true,
    });

    const onRefreshed = (event: MessageEvent) => {
      void queryClient.invalidateQueries({ queryKey: portfolioKeys.all });
      if (notify) {
        try {
          const payload = JSON.parse(event.data) as MarketRefreshedEvent;
          toast.info(t('portfolio.data_refreshed', { kind: payload.kind }));
        } catch {
          /* heartbeat or malformed payload — ignore */
        }
      }
    };

    source.addEventListener('data_refreshed', onRefreshed as EventListener);
    return () => {
      source.removeEventListener('data_refreshed', onRefreshed as EventListener);
      source.close();
    };
  }, [queryClient, t, notify]);
}
