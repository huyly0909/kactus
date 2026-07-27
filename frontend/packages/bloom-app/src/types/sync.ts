/** Sync-job queue — the shared FIFO orchestration for the single DuckDB writer.
 *
 * Gold is the first consumer (backfill + sync-now). Numeric fields arrive as
 * strings (backend FancyInt → string in JSON) to dodge JS precision loss. */

export type GoldSource = 'sjc' | 'yahoo' | 'mihong';
export type GoldSyncSource = GoldSource | 'all';

export type SyncJobStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';

/** A job in one of these blocks a duplicate enqueue and disables its trigger. */
export function isActiveStatus(status: string): boolean {
  return status === 'pending' || status === 'running';
}

export interface SyncJob {
  id: string;
  job_type: string;
  dedup_key: string;
  params: Record<string, unknown>;
  status: SyncJobStatus;
  progress_total: string;
  progress_done: string;
  progress_pct: string;
  cursor?: string | null;
  message?: string | null;
  result?: Record<string, unknown> | null;
  created_by?: string | null;
  create_time?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface SyncJobList {
  /** Live jobs (pending/running), oldest first — the queue as it will run. */
  active: SyncJob[];
  /** Most-recent jobs regardless of status (may repeat an active row). */
  recent: SyncJob[];
}

export interface EnqueueSyncJobResponse {
  job: SyncJob;
  /** `false` → an identical job was already live and this click was collapsed. */
  created: boolean;
}

export interface GoldBackfillRequest {
  source: GoldSource;
  /** Domestic code override (Mihong only); SJC/Yahoo force their own. */
  code?: string;
  /** YYYY-MM-DD. */
  date_from: string;
  date_to: string;
}

export interface GoldSyncRequest {
  source?: GoldSyncSource;
}

/** SSE `sync.progress` frame. It rides the portfolio stream (which labels every
 * message `data_refreshed`), so the client discriminates on `event`. Mirrors
 * `kactus_data.jobs.sync_queue._publish`. */
export interface SyncProgressEvent {
  event: 'sync.progress';
  job_id: string;
  job_type: string;
  dedup_key: string;
  status: SyncJobStatus;
  done: number;
  total: number;
  pct: number;
}

/** Earliest backfillable date per source — mirrors `kactus_common.sync.gold`.
 * Mihong is a trailing window with no fixed floor (null → resolved from today). */
export const GOLD_BACKFILL_MIN: Record<GoldSource, string | null> = {
  sjc: '2009-07-22',
  yahoo: '2000-08-30',
  mihong: null,
};

export const MIHONG_BACKFILL_DAYS = 365;

/** "YYYY-MM-DD" from local date parts (no UTC shift near midnight). */
function fmtLocal(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** The earliest date a source can backfill, resolving Mihong's trailing window. */
export function resolveGoldBackfillMin(source: GoldSource): string {
  const fixed = GOLD_BACKFILL_MIN[source];
  if (fixed) return fixed;
  const d = new Date();
  d.setDate(d.getDate() - MIHONG_BACKFILL_DAYS);
  return fmtLocal(d);
}

/** Today as YYYY-MM-DD (local) — the natural upper bound for "all". */
export function todayLocal(): string {
  return fmtLocal(new Date());
}

/** Whether a live dedup_key touches `source` — a per-source or an all-sources
 * job both make that source busy (single DuckDB writer). */
export function dedupKeyTouchesSource(dedupKey: string, source: GoldSource): boolean {
  return (
    dedupKey.startsWith(`gold_backfill:${source}`) ||
    dedupKey === `gold_sync:${source}` ||
    dedupKey === 'gold_sync:all'
  );
}
