// Format seam for ReportView cells. Builtiful routed money/qty/date through
// <Monetary>/<Quantity>/useFormatters wired to the active company's currency;
// kactus has no company currency, so cells format through the existing
// lib/format helpers (VND-friendly, thousands-separated). One place to change
// if a locale/currency layer ever lands.

import { fmt, fmtCompact, fmtDateTime } from '@/lib/format';
import type { ReportCellKind } from './types';

export function formatCell(kind: ReportCellKind | undefined, value: unknown): string {
  if (value == null || value === '') return '—';
  switch (kind) {
    case 'number':
      return fmt(value as number | string);
    case 'money':
      return fmtCompact(value as number | string);
    case 'date':
      return fmtDateTime(value as string);
    default:
      return String(value);
  }
}
