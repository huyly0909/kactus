/** Scheduler read models — the recurring APScheduler cron jobs that live in the
 * data plane, surfaced read-only via `GET /api/admin/portfolios/crawl-status`.
 * Mirrors `kactus_common.portfolio.schema.CrawlStatusSchema` / `CrawlJobSchema`. */

export interface CrawlJob {
  id: string;
  name?: string | null;
  /** Raw `str(trigger)` — the fallback when `cron` is absent. */
  cadence?: string | null;
  /** Cron fields, wildcards dropped (`{day_of_week, hour, minute}`). A missing
   * `day_of_week` means every day, weekends included. */
  cron?: Record<string, string> | null;
  /** Timezone the `cron` fields are expressed in — NOT UTC (the scheduler runs
   * on `Asia/Ho_Chi_Minh`). */
  timezone?: string | null;
  /** UTC ISO instant of the next fire, or null when paused / not scheduled. */
  next_run_time?: string | null;
  /** Scheduler is running but this job has no next fire time. */
  paused: boolean;
}

export interface CrawlStatus {
  scheduler_running: boolean;
  vnstock_tier?: string | null;
  jobs: CrawlJob[];
}
