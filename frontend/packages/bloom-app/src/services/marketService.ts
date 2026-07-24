import { apiClient } from './apiClient';
import type { ApiResponse } from '@/types/api';
import type {
  FinanceReport,
  GoldPrice,
  OHLCV,
  OHLCVInterval,
  ReportPeriod,
  ReportType,
  StockDetail,
  StockListing,
  StockNews,
  StockQuote,
} from '@/types/market';

export interface OHLCVParams {
  interval?: OHLCVInterval;
  start?: string;
  end?: string;
  limit?: number;
}

export interface FinanceParams {
  report_type: ReportType;
  period?: ReportPeriod;
  limit?: number;
}

/** Market service — read-only access to the crawled gold / stock / finance data. */
export const marketService = {
  gold: async (codes?: string[]): Promise<GoldPrice[]> => {
    const { data } = await apiClient.get<ApiResponse<GoldPrice[]>>('/api/market/gold', {
      params: codes?.length ? { code: codes } : undefined,
    });
    return data.data;
  },

  searchStocks: async (q?: string, limit = 50): Promise<StockListing[]> => {
    const { data } = await apiClient.get<ApiResponse<StockListing[]>>('/api/market/stocks', {
      params: { q: q || undefined, limit },
    });
    return data.data;
  },

  quotes: async (symbols?: string[]): Promise<StockQuote[]> => {
    const { data } = await apiClient.get<ApiResponse<StockQuote[]>>('/api/market/stocks/quotes', {
      params: symbols?.length ? { symbol: symbols } : undefined,
    });
    return data.data;
  },

  stock: async (symbol: string): Promise<StockDetail> => {
    const { data } = await apiClient.get<ApiResponse<StockDetail>>(`/api/market/stocks/${symbol}`);
    return data.data;
  },

  ohlcv: async (symbol: string, params: OHLCVParams = {}): Promise<OHLCV[]> => {
    const { data } = await apiClient.get<ApiResponse<OHLCV[]>>(
      `/api/market/stocks/${symbol}/ohlcv`,
      { params },
    );
    return data.data;
  },

  news: async (symbol: string, limit = 20): Promise<StockNews[]> => {
    const { data } = await apiClient.get<ApiResponse<StockNews[]>>(
      `/api/market/stocks/${symbol}/news`,
      { params: { limit } },
    );
    return data.data;
  },

  finance: async (symbol: string, params: FinanceParams): Promise<FinanceReport[]> => {
    const { data } = await apiClient.get<ApiResponse<FinanceReport[]>>(
      `/api/market/stocks/${symbol}/finance`,
      { params },
    );
    return data.data;
  },
};
