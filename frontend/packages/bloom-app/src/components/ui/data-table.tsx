import { useMemo, useState } from 'react';
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table';
import { Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

/** Simple column descriptor — mirrors the legacy `bloom-ui` DataTable API. */
export interface DataTableColumn<T> {
  key: string;
  title: React.ReactNode;
  render?: (record: T, index: number) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  loading?: boolean;
  searchable?: boolean;
  searchPlaceholder?: string;
  pageSize?: number;
  emptyMessage?: string;
  getRowKey?: (record: T, index: number) => string | number;
  onRowClick?: (record: T) => void;
}

/**
 * Generic table — client-side search + pagination + custom column rendering.
 * Built on `@tanstack/react-table` + the shadcn `Table` primitives.
 * shadcn replacement for the legacy Mantine `bloom-ui/DataTable`.
 */
export function DataTable<T>({
  columns,
  data,
  loading = false,
  searchable = true,
  searchPlaceholder = 'Search...',
  pageSize = 10,
  emptyMessage = 'No data found',
  getRowKey,
  onRowClick,
}: DataTableProps<T>) {
  const [globalFilter, setGlobalFilter] = useState('');

  const columnDefs = useMemo<ColumnDef<T>[]>(
    () =>
      columns.map((col) => ({
        id: col.key,
        accessorFn: (row) => (row as Record<string, unknown>)[col.key],
        header: () => col.title,
        cell: ({ row }) =>
          col.render
            ? col.render(row.original, row.index)
            : String((row.original as Record<string, unknown>)[col.key] ?? ''),
        meta: { className: col.className },
      })),
    [columns],
  );

  const table = useReactTable({
    data,
    columns: columnDefs,
    state: { globalFilter },
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
    getRowId: getRowKey ? (row, index) => String(getRowKey(row, index)) : undefined,
  });

  if (loading) {
    return <Skeleton className="h-40 w-full" />;
  }

  const rows = table.getRowModel().rows;
  const pageCount = table.getPageCount();

  return (
    <div className="space-y-3">
      {searchable && (
        <div className="relative max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            placeholder={searchPlaceholder}
            className="pl-8"
          />
        </div>
      )}

      <div className="rounded-md border border-border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id} className="border-t-0">
                {hg.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className={(header.column.columnDef.meta as { className?: string })?.className}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="py-8 text-center text-muted-foreground"
                >
                  {emptyMessage}
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow
                  key={row.id}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  className={cn(onRowClick && 'cursor-pointer')}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className={(cell.column.columnDef.meta as { className?: string })?.className}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {pageCount > 1 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {table.getState().pagination.pageIndex + 1} / {pageCount}
          </span>
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
