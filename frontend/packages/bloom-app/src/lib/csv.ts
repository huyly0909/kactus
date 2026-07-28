// Tiny dependency-free CSV writer used by the DataTable export action.

/** RFC-4180 cell escaping: wrap in quotes when the value contains a comma,
 *  quote or newline, doubling any embedded quotes. */
export function escapeCSVCell(value: unknown): string {
  const s = value == null ? '' : String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Build a CSV string from a header row + body rows (CRLF line breaks). A
 *  body with no rows returns the header line alone. */
export function toCSV(headers: string[], rows: (string | number | null | undefined)[][]): string {
  const head = headers.map(escapeCSVCell).join(',');
  if (rows.length === 0) return head;
  const body = rows.map((r) => r.map(escapeCSVCell).join(',')).join('\r\n');
  return `${head}\r\n${body}`;
}

/** Trigger a client-side download of `csv` as `filename`. Prepends a BOM so
 *  Excel opens UTF-8 (Vietnamese) correctly. No-op outside the browser. */
export function downloadCSV(filename: string, csv: string): void {
  if (typeof document === 'undefined') return;
  const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
