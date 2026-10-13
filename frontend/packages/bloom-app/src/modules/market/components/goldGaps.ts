/** Gap / staleness detection for a gold history series, driven by its
 * data-availability schedule (`global_settings`). Pure functions, no React —
 * unit-tested in `goldGaps.test.ts`.
 *
 * Weekdays follow Python `weekday()`: **Mon=0 … Sun=6**, matching the backend.
 * All date maths runs on "YYYY-MM-DD" calendar strings parsed as UTC parts, so
 * the browser's timezone can never shift a day; "today" is resolved in the
 * schedule's own market timezone via `Intl`, never the browser clock. */

import type { GoldHistoryPoint, GoldScheduleResponse } from '@/types/market';

const DAY_MS = 86_400_000;

/** Python `weekday()` for a "YYYY-MM-DD" string (Mon=0 … Sun=6), timezone-neutral. */
export function weekdayOf(dateStr: string): number {
  const [y, m, d] = dateStr.split('-').map(Number);
  const js = new Date(Date.UTC(y, (m ?? 1) - 1, d ?? 1)).getUTCDay(); // Sun=0 … Sat=6
  return (js + 6) % 7;
}

/** Today as "YYYY-MM-DD" in `tz` (the schedule's market zone, NOT the browser).
 * `en-CA` renders an ISO calendar date; `Intl` places it in the requested zone. */
export function todayInTz(tz: string): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: tz }).format(new Date());
}

/** Inclusive "YYYY-MM-DD" calendar range (UTC parts → no browser-zone drift).
 * Empty when either bound is missing or `from` > `to`. */
function eachDay(from: string, to: string): string[] {
  if (!from || !to || from > to) return [];
  const [fy, fm, fd] = from.split('-').map(Number);
  const [ty, tm, td] = to.split('-').map(Number);
  let cur = Date.UTC(fy, (fm ?? 1) - 1, fd ?? 1);
  const end = Date.UTC(ty, (tm ?? 1) - 1, td ?? 1);
  const out: string[] = [];
  while (cur <= end) {
    out.push(new Date(cur).toISOString().slice(0, 10));
    cur += DAY_MS;
  }
  return out;
}

/** Dates in [from, to] the schedule expects data on: weekday ∈ expected_weekdays,
 * minus the schedule's holidays. */
export function expectedDays(from: string, to: string, schedule: GoldScheduleResponse): string[] {
  const holidays = new Set(schedule.holidays ?? []);
  const wanted = new Set(schedule.expected_weekdays);
  return eachDay(from, to).filter((d) => wanted.has(weekdayOf(d)) && !holidays.has(d));
}

function earliestDate(points: GoldHistoryPoint[]): string | null {
  let min: string | null = null;
  for (const p of points) if (min === null || p.date < min) min = p.date;
  return min;
}

/**
 * Expected trading days within the covered window that carry no data point.
 * Excludes today, which `todayMissing` owns (so the two chips never double-count).
 *
 * Bounds are clamped to the window the response actually covers — the backend
 * keeps only the most recent rows past its cap, cutting the *old* end, so a
 * request wider than the data must not invent a gap before the earliest point:
 *  - lower = later of (`from`, earliest point); empty `from` ⇒ earliest point
 *  - upper = today in the schedule's timezone (the tail is intact), capped by `to`
 */
export function detectGaps(
  points: GoldHistoryPoint[],
  from: string,
  to: string,
  schedule: GoldScheduleResponse,
): string[] {
  const earliest = earliestDate(points);
  if (earliest === null) return [];
  const today = todayInTz(schedule.timezone);
  const lower = from && from > earliest ? from : earliest;
  const upper = to && to < today ? to : today;
  const present = new Set(points.map((p) => p.date));
  return expectedDays(lower, upper, schedule).filter((d) => d !== today && !present.has(d));
}

/** Whether today (in the schedule's timezone) is an expected trading day that
 * still has no data point. */
export function todayMissing(points: GoldHistoryPoint[], schedule: GoldScheduleResponse): boolean {
  const today = todayInTz(schedule.timezone);
  if (!schedule.expected_weekdays.includes(weekdayOf(today))) return false;
  if ((schedule.holidays ?? []).includes(today)) return false;
  return !points.some((p) => p.date === today);
}
