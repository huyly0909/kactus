import { isValidElement, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatCell } from './format';
import { ColumnDebug } from './column-debug';
import type { ReportColumn, ReportRow, ReportViewProps } from './types';

function alignClass(align?: 'left' | 'center' | 'right'): string {
  if (align === 'right') return 'text-right';
  if (align === 'center') return 'text-center';
  return 'text-left';
}

// Per-row-kind chrome. The grid is identical across kinds; only weight, borders
// and background separate a section header from a data line from a grand total.
const ROW_KIND_CLASS: Record<ReportRow['kind'], string> = {
  section: 'bg-muted/40 font-semibold text-foreground',
  data: '',
  subtotal: 'border-t border-border font-medium',
  total: 'border-t-2 border-border bg-muted/30 font-bold',
  opening: 'italic text-muted-foreground',
  spacer: '',
};

function renderValue(col: ReportColumn, raw: unknown) {
  if (raw == null) return formatCell(col.kind, raw);
  if (isValidElement(raw)) return raw;
  return formatCell(col.kind, raw);
}

/**
 * ReportView — a heterogeneous-row report/pivot table. Section headers, data
 * lines, subtotals, a grand total and opening balances share one column grid;
 * sections can collapse their child rows. The caller supplies already-shaped
 * rows + columns (no data-source coupling); cell formatting goes through the
 * format seam (see format.ts).
 */
export function ReportView({
  columns,
  rows,
  rowHeaderLabel,
  loading = false,
  emptyMessage = 'No data',
  className,
}: ReportViewProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const toggle = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  if (loading) return <Skeleton className={cn('h-64 w-full', className)} />;

  const totalCols = columns.length + 1;
  const visibleRows = rows.filter((r) => !(r.groupId && collapsed.has(r.groupId)));

  return (
    <div className={cn('rounded-md border border-border overflow-x-auto', className)}>
      <Table>
        <TableHeader>
          <TableRow className="border-t-0">
            <TableHead className="min-w-56">
              {rowHeaderLabel}
              <ColumnDebug id="__row_header" />
            </TableHead>
            {columns.map((col) => (
              <TableHead
                key={col.id}
                className={cn('whitespace-nowrap', alignClass(col.align ?? 'right'), col.className)}
              >
                {col.header}
                <ColumnDebug id={col.id} />
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleRows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={totalCols} className="py-8 text-center text-muted-foreground">
                {emptyMessage}
              </TableCell>
            </TableRow>
          ) : (
            visibleRows.map((row) => {
              if (row.kind === 'spacer') {
                return (
                  <TableRow key={row.id} className="hover:bg-transparent">
                    <TableCell colSpan={totalCols} className="h-2 p-0" />
                  </TableRow>
                );
              }
              const isCollapsed = collapsed.has(row.id);
              return (
                <TableRow key={row.id} className={ROW_KIND_CLASS[row.kind]}>
                  <TableCell
                    className={cn(row.collapsible && 'cursor-pointer select-none')}
                    style={{ paddingLeft: row.depth ? `${row.depth * 1.25 + 1}rem` : undefined }}
                    onClick={row.collapsible ? () => toggle(row.id) : undefined}
                  >
                    <span className="inline-flex items-center gap-1">
                      {row.collapsible && (
                        <ChevronRight
                          className={cn(
                            'h-3.5 w-3.5 shrink-0 transition-transform',
                            !isCollapsed && 'rotate-90',
                          )}
                        />
                      )}
                      {row.label}
                    </span>
                  </TableCell>
                  {columns.map((col) => (
                    <TableCell
                      key={col.id}
                      className={cn(
                        'tabular-nums whitespace-nowrap',
                        alignClass(col.align ?? 'right'),
                        col.className,
                      )}
                    >
                      {renderValue(col, row.values?.[col.id])}
                    </TableCell>
                  ))}
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </div>
  );
}
