import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { portfolioService, type CreatePortfolioBody } from '@/services/portfolioService';
import type { AssetType, CrawlKind } from '@/types/portfolio';

/** Query key factory — the single source of cache keys for the feature. */
export const portfolioKeys = {
  all: ['portfolios'] as const,
  lists: () => [...portfolioKeys.all, 'list'] as const,
  detail: (id: string) => [...portfolioKeys.all, 'detail', id] as const,
  quotes: (id: string) => [...portfolioKeys.all, 'quotes', id] as const,
  news: (id: string) => [...portfolioKeys.all, 'news', id] as const,
  assets: (params: Record<string, unknown>) => ['assets', 'supported', params] as const,
};

// ----------------------------------------------------------------- queries
export function usePortfolios() {
  return useQuery({
    queryKey: portfolioKeys.lists(),
    queryFn: portfolioService.list,
  });
}

export function usePortfolio(id: string) {
  return useQuery({
    queryKey: portfolioKeys.detail(id),
    queryFn: () => portfolioService.get(id),
    enabled: !!id,
  });
}

export function usePortfolioQuotes(id: string) {
  return useQuery({
    queryKey: portfolioKeys.quotes(id),
    queryFn: () => portfolioService.quotes(id),
    enabled: !!id,
  });
}

export function usePortfolioNews(id: string) {
  return useQuery({
    queryKey: portfolioKeys.news(id),
    queryFn: () => portfolioService.news(id),
    enabled: !!id,
  });
}

export function useAssetSearch(params: { asset_type?: AssetType; q?: string; tag?: string }) {
  return useQuery({
    queryKey: portfolioKeys.assets(params),
    queryFn: () => portfolioService.searchAssets({ ...params, limit: 20 }),
    enabled: !!(params.q && params.q.length >= 1),
  });
}

// --------------------------------------------------------------- mutations
export function useCreatePortfolio() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (body: CreatePortfolioBody) => portfolioService.create(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: portfolioKeys.lists() });
      toast.success(t('common.create_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

export function useUpdatePortfolio(id: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (body: Partial<CreatePortfolioBody>) => portfolioService.update(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: portfolioKeys.lists() });
      void qc.invalidateQueries({ queryKey: portfolioKeys.detail(id) });
      toast.success(t('common.update_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

export function useDeletePortfolio() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (id: string) => portfolioService.remove(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: portfolioKeys.lists() });
      toast.success(t('common.delete_success'));
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}

export function useAddItem(id: string) {
  const qc = useQueryClient();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (body: { asset_type: AssetType; code: string }) =>
      portfolioService.addItem(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: portfolioKeys.detail(id) });
      void qc.invalidateQueries({ queryKey: portfolioKeys.quotes(id) });
      toast.success(t('portfolio.item_added'));
    },
    onError: () => toast.error(t('portfolio.item_add_error')),
  });
}

export function useRemoveItem(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ asset_type, code }: { asset_type: AssetType; code: string }) =>
      portfolioService.removeItem(id, asset_type, code),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: portfolioKeys.detail(id) });
      void qc.invalidateQueries({ queryKey: portfolioKeys.quotes(id) });
    },
  });
}

export function useRefreshPortfolio(id: string) {
  const { t } = useTranslation();
  return useMutation({
    mutationFn: (kind: CrawlKind = 'quotes') => portfolioService.refresh(id, kind),
    onSuccess: (result) => {
      if (result.skipped) {
        toast.info(t('portfolio.refresh_in_progress'));
      } else {
        toast.success(t('portfolio.refresh_scheduled'));
      }
    },
    onError: () => toast.error(t('common.error_generic')),
  });
}
