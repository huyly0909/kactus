import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  marketService,
  type FinanceParams,
  type GoldHistoryParams,
  type OHLCVParams,
} from '@/services/marketService';

/** Query key factory — the single source of cache keys for the market feature. */
export const marketKeys = {
  all: ['market'] as const,
  gold: () => [...marketKeys.all, 'gold'] as const,
  goldHistoryAll: () => [...marketKeys.all, 'gold-history'] as const,
  goldHistory: (code: string, params: GoldHistoryParams) =>
    [...marketKeys.goldHistoryAll(), code, params] as const,
  goldHistoryCodes: () => [...marketKeys.goldHistoryAll(), 'codes'] as const,
  stocks: (q: string) => [...marketKeys.all, 'stocks', q] as const,
  quotes: (symbols: string[]) => [...marketKeys.all, 'quotes', symbols] as const,
  stock: (symbol: string) => [...marketKeys.all, 'stock', symbol] as const,
  ohlcv: (symbol: string, params: OHLCVParams) =>
    [...marketKeys.all, 'ohlcv', symbol, params] as const,
  news: (symbol: string) => [...marketKeys.all, 'news', symbol] as const,
  finance: (symbol: string, params: FinanceParams) =>
    [...marketKeys.all, 'finance', symbol, params] as const,
};

export function useGoldPrices() {
  return useQuery({
    queryKey: marketKeys.gold(),
    queryFn: () => marketService.gold(),
  });
}

export function useGoldHistory(code: string, params: GoldHistoryParams = {}) {
  return useQuery({
    queryKey: marketKeys.goldHistory(code, params),
    queryFn: () => marketService.goldHistory(code, params),
    enabled: !!code,
  });
}

export function useGoldHistoryCodes() {
  return useQuery({
    queryKey: marketKeys.goldHistoryCodes(),
    queryFn: () => marketService.goldHistoryCodes(),
  });
}

export function useImportGoldHistory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => marketService.importGoldHistory(files),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: marketKeys.goldHistoryAll() });
    },
  });
}

export function useStockSearch(q: string) {
  return useQuery({
    queryKey: marketKeys.stocks(q),
    queryFn: () => marketService.searchStocks(q),
  });
}

export function useStockQuotes(symbols: string[]) {
  return useQuery({
    queryKey: marketKeys.quotes(symbols),
    queryFn: () => marketService.quotes(symbols),
    enabled: symbols.length > 0,
  });
}

export function useStock(symbol: string) {
  return useQuery({
    queryKey: marketKeys.stock(symbol),
    queryFn: () => marketService.stock(symbol),
    enabled: !!symbol,
    retry: false,
  });
}

export function useOHLCV(symbol: string, params: OHLCVParams) {
  return useQuery({
    queryKey: marketKeys.ohlcv(symbol, params),
    queryFn: () => marketService.ohlcv(symbol, params),
    enabled: !!symbol,
  });
}

export function useStockNews(symbol: string) {
  return useQuery({
    queryKey: marketKeys.news(symbol),
    queryFn: () => marketService.news(symbol),
    enabled: !!symbol,
  });
}

export function useFinanceReports(symbol: string, params: FinanceParams) {
  return useQuery({
    queryKey: marketKeys.finance(symbol, params),
    queryFn: () => marketService.finance(symbol, params),
    enabled: !!symbol,
  });
}
