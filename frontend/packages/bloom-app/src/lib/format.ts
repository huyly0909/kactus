/** Formatting helpers for API numbers, which arrive as strings (FancyInt/FancyFloat). */

/** Parse an API numeric string; returns null for null/empty/NaN. */
export function num(v?: string | number | null): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

/** Locale-formatted number, or an em dash when missing. */
export function fmt(v?: string | number | null, digits?: number): string {
  const n = num(v);
  if (n == null) return '—';
  return n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Compact notation for large magnitudes (market cap, volume). */
export function fmtCompact(v?: string | number | null): string {
  const n = num(v);
  if (n == null) return '—';
  return n.toLocaleString(undefined, { notation: 'compact', maximumFractionDigits: 2 });
}

/** Tailwind text colour for a gain/loss delta. */
export function toneOf(v?: string | number | null): string {
  const n = num(v);
  if (n == null || n === 0) return '';
  return n > 0 ? 'text-[var(--gain)]' : 'text-[var(--loss)]';
}

/** Signed delta with an optional percentage, e.g. `+1.20 (2.40%)`. */
export function fmtChange(change?: string | number | null, pct?: string | number | null): string {
  const c = num(change);
  if (c == null) return '—';
  const sign = c > 0 ? '+' : '';
  const p = num(pct);
  return p == null ? `${sign}${c.toFixed(2)}` : `${sign}${c.toFixed(2)} (${p.toFixed(2)}%)`;
}

/** Short date-time for crawl/sync timestamps. */
export function fmtDateTime(v?: string | null): string {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString();
}
