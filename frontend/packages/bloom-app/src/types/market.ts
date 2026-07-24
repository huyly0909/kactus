/** Market (gold / stock / finance) read models served from the OLAP store.
 *
 * Numeric values arrive as strings: the backend serialises FancyInt/FancyFloat
 * to strings in JSON to avoid JS precision loss. */

export type ReportType = 'income_statement' | 'balance_sheet' | 'cash_flow' | 'ratio';
export type ReportPeriod = 'year' | 'quarter';
export type OHLCVInterval = '1m' | '5m' | '15m' | '30m' | '1H' | '1D' | '1W' | '1M';

export interface GoldPrice {
  code: string;
  buy_price?: string | null;
  sell_price?: string | null;
  spread?: string | null;
  source?: string | null;
  crawled_at?: string | null;
}

export interface StockListing {
  symbol: string;
  organ_name?: string | null;
  source?: string | null;
  synced_at?: string | null;
}

export interface StockQuote {
  symbol: string;
  match_price?: string | null;
  ref_price?: string | null;
  ceiling?: string | null;
  floor?: string | null;
  accumulated_volume?: string | null;
  change?: string | null;
  change_pct?: string | null;
  source?: string | null;
  crawled_at?: string | null;
}

export interface Company {
  symbol: string;
  company_name?: string | null;
  short_name?: string | null;
  industry?: string | null;
  exchange?: string | null;
  market_cap?: string | null;
  outstanding_shares?: string | null;
  source?: string | null;
  synced_at?: string | null;
}

export interface StockDetail {
  symbol: string;
  organ_name?: string | null;
  company?: Company | null;
  quote?: StockQuote | null;
}

export interface OHLCV {
  symbol: string;
  time: string;
  interval: string;
  open?: string | null;
  high?: string | null;
  low?: string | null;
  close?: string | null;
  volume?: string | null;
  source?: string | null;
}

export interface StockNews {
  symbol: string;
  news_id?: string | null;
  title?: string | null;
  published_at?: string | null;
  url?: string | null;
  source?: string | null;
}

export interface FinanceReport {
  symbol: string;
  report_type: ReportType;
  period: ReportPeriod;
  year: string;
  quarter?: string | null;
  /** Full source row — vnstock's columns differ per report type and source. */
  data: Record<string, unknown>;
  source?: string | null;
  synced_at?: string | null;
}
