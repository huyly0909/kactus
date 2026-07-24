/** Portfolio feature types (asset-class agnostic).
 *
 * Numeric values arrive as strings: the backend serialises FancyInt/FancyFloat
 * to strings in JSON to avoid JS precision loss. */

export type AssetType = 'STOCK' | 'GOLD' | 'COIN';
export type CrawlKind = 'quotes' | 'news' | 'foreign_trade' | 'ratios' | 'events' | 'ohlcv';

export interface Portfolio {
  id: string;
  name: string;
  description?: string | null;
  owner_id: string;
}

export interface PortfolioItem {
  id: string;
  portfolio_id: string;
  asset_type: AssetType;
  code: string;
}

export interface PortfolioDetail extends Portfolio {
  items: PortfolioItem[];
}

export interface SupportedAsset {
  id: string;
  asset_type: AssetType;
  code: string;
  name?: string | null;
  is_crawlable: boolean;
  tags: string[];
  meta_json: Record<string, unknown>;
}

export interface MarketQuote {
  asset_type: AssetType;
  code: string;
  match_price?: string | null;
  ref_price?: string | null;
  ceiling?: string | null;
  floor?: string | null;
  buy_price?: string | null;
  sell_price?: string | null;
  /** Price unit for gold rows (`VND/luong` vs `USD/oz`); absent for stocks. */
  unit?: string | null;
  volume?: string | null;
  source?: string | null;
  crawled_at?: string | null;
}

export interface MarketNews {
  symbol: string;
  news_id?: string | null;
  title?: string | null;
  published_at?: string | null;
  url?: string | null;
  source?: string | null;
}

export interface CrawlTriggerResult {
  crawl_run_ids: string[];
  skipped: boolean;
  message: string;
}

export interface MarketRefreshedEvent {
  asset_type: string;
  kind: string;
  codes: string[];
  crawl_run_id?: number | null;
}
