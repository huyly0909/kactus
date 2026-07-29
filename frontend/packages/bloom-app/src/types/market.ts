/** Market (gold / stock / finance) read models served from the OLAP store.
 *
 * Numeric values arrive as strings: the backend serialises FancyInt/FancyFloat
 * to strings in JSON to avoid JS precision loss. */

export type ReportType = 'income_statement' | 'balance_sheet' | 'cash_flow' | 'ratio';
export type ReportPeriod = 'year' | 'quarter';
export type OHLCVInterval = '1m' | '5m' | '15m' | '30m' | '1H' | '1D' | '1W' | '1M';

/** Price unit markers emitted by the gold board (`kactus_data` portfolio_tables). */
export const UNIT_VND_PER_LUONG = 'VND/luong';
export const UNIT_USD_PER_OZ = 'USD/oz';

/** One board row. Identity is `(code, source)` — `code` alone is NOT unique:
 *  SJC and mihong both quote 999 as different products, so the board returns
 *  a row for each. Key lists/maps on both fields. */
export interface GoldPrice {
  code: string;
  buy_price?: string | null;
  sell_price?: string | null;
  spread?: string | null;
  /** `VND/luong` (domestic) or `USD/oz` (world) — the board mixes both. */
  unit?: string | null;
  source?: string | null;
  crawled_at?: string | null;
}

export interface GoldHistoryPoint {
  code: string;
  date: string;
  buy_price?: string | null;
  sell_price?: string | null;
  open?: string | null;
  high?: string | null;
  low?: string | null;
  close?: string | null;
  /** `VND/luong` (domestic) or `USD/oz` (world) — never mix on one axis. */
  unit: string;
  source?: string | null;
  location?: string | null;
  gold_type?: string | null;
}

export interface GoldHistoryCode {
  code: string;
  unit: string;
  points: string;
  first_date?: string | null;
  last_date?: string | null;
  location?: string | null;
  gold_type?: string | null;
}

/** Market operating timezone a schedule is interpreted in — only these two are
 * supported for now (matches backend `ScheduleTimezone`). Distinct from the
 * user's *display* timezone: this is when the source is expected to have data. */
export type ScheduleTimezone = 'UTC' | 'Asia/Ho_Chi_Minh';

/** Data-availability schedule for one gold series — drives the gap / stale
 * chips. Weekdays are Python `weekday()`: Mon=0 … Sun=6. `holidays` are calendar
 * dates ("YYYY-MM-DD") in the schedule's own `timezone`. */
export interface GoldScheduleResponse {
  source: string;
  code: string;
  expected_weekdays: number[];
  holidays?: string[];
  timezone: ScheduleTimezone;
  enabled: boolean;
}

export interface GoldImportResult {
  dataset: string;
  filename?: string | null;
  rows_parsed: string;
  rows_imported: string;
  rows_skipped: string;
  codes: string;
  errors: string[];
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
  /** Canonical UTC instant (`+00:00`), derived from the native VN-local bar time. */
  event_dt?: string | null;
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
