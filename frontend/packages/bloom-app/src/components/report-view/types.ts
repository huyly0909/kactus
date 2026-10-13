import type { ReactNode } from 'react';

/** How a value column's cells are formatted (via the format seam). */
export type ReportCellKind = 'text' | 'number' | 'money' | 'date';

export interface ReportColumn {
  id: string;
  header: ReactNode;
  align?: 'left' | 'center' | 'right';
  /** Cell formatting; defaults to 'text'. */
  kind?: ReportCellKind;
  /** Extra classes for this column's <td>/<th>. */
  className?: string;
}

/** Row archetypes — the heterogeneous-row model is the whole point of a report
 *  table (a section header, a data line, a subtotal and a grand total all share
 *  one column grid but read differently). */
export type ReportRowKind = 'section' | 'data' | 'subtotal' | 'total' | 'opening' | 'spacer';

export interface ReportRow {
  id: string;
  kind: ReportRowKind;
  /** Label rendered in the leading row-header column. */
  label?: ReactNode;
  /** Cell values keyed by column id — a primitive (formatted per column.kind)
   *  or a ready-made node. */
  values?: Record<string, ReactNode | number | string | null | undefined>;
  /** Tree indentation depth for the label. */
  depth?: number;
  /** A collapsible section toggles the visibility of rows whose `groupId`
   *  equals the section's `id`. */
  collapsible?: boolean;
  groupId?: string;
}

export interface ReportViewProps {
  columns: ReportColumn[];
  rows: ReportRow[];
  /** Header for the leading row-header column. */
  rowHeaderLabel?: ReactNode;
  loading?: boolean;
  emptyMessage?: string;
  className?: string;
}
