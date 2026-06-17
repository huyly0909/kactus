import { apiClient } from './apiClient';
import type { ApiResponse } from '@/types/api';
import type {
  AssetType,
  CrawlKind,
  CrawlTriggerResult,
  MarketNews,
  MarketQuote,
  Portfolio,
  PortfolioDetail,
  PortfolioItem,
  SupportedAsset,
} from '@/types/portfolio';

/** Backend pagination envelope (snake_case, matches kactus-common Pagination). */
interface ListEnvelope<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface CreatePortfolioBody {
  name: string;
  description?: string;
}

export const portfolioService = {
  list: async (): Promise<Portfolio[]> => {
    const { data } = await apiClient.get<ApiResponse<ListEnvelope<Portfolio>>>('/api/portfolios');
    return data.data.items;
  },

  get: async (id: string): Promise<PortfolioDetail> => {
    const { data } = await apiClient.get<ApiResponse<PortfolioDetail>>(`/api/portfolios/${id}`);
    return data.data;
  },

  create: async (body: CreatePortfolioBody): Promise<Portfolio> => {
    const { data } = await apiClient.post<ApiResponse<Portfolio>>('/api/portfolios', body);
    return data.data;
  },

  update: async (id: string, body: Partial<CreatePortfolioBody>): Promise<Portfolio> => {
    const { data } = await apiClient.put<ApiResponse<Portfolio>>(`/api/portfolios/${id}`, body);
    return data.data;
  },

  remove: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/portfolios/${id}`);
  },

  addItem: async (
    id: string,
    body: { asset_type: AssetType; code: string },
  ): Promise<PortfolioItem> => {
    const { data } = await apiClient.post<ApiResponse<PortfolioItem>>(
      `/api/portfolios/${id}/items`,
      body,
    );
    return data.data;
  },

  removeItem: async (id: string, asset_type: AssetType, code: string): Promise<void> => {
    await apiClient.delete(`/api/portfolios/${id}/items`, { params: { asset_type, code } });
  },

  quotes: async (id: string): Promise<MarketQuote[]> => {
    const { data } = await apiClient.get<ApiResponse<MarketQuote[]>>(
      `/api/portfolios/${id}/quotes`,
    );
    return data.data;
  },

  news: async (id: string): Promise<MarketNews[]> => {
    const { data } = await apiClient.get<ApiResponse<MarketNews[]>>(`/api/portfolios/${id}/news`);
    return data.data;
  },

  refresh: async (id: string, kind: CrawlKind = 'quotes'): Promise<CrawlTriggerResult> => {
    const { data } = await apiClient.post<ApiResponse<CrawlTriggerResult>>(
      `/api/portfolios/${id}/refresh`,
      null,
      { params: { kind } },
    );
    return data.data;
  },

  searchAssets: async (params: {
    asset_type?: AssetType;
    q?: string;
    tag?: string;
    limit?: number;
  }): Promise<SupportedAsset[]> => {
    const { data } = await apiClient.get<ApiResponse<ListEnvelope<SupportedAsset>>>(
      '/api/assets/supported',
      { params },
    );
    return data.data.items;
  },
};
