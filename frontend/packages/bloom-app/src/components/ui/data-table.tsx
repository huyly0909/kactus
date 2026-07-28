import { useMemo, useState } from 'react';
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
  type VisibilityState,
} from '@tanstack/react-table';
import {
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  Download,
  SlidersHorizontal,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useIsDesktop } from '@/hooks/use-media-query';
import { toCSV, downloadCSV } from '@/lib/csv';

/** Simple column descriptor — mirrors the legacy `bloom-ui` DataTable API.
 *  Every field past `className` is additive and optional. */
export interface DataTableColumn<T> {
  key: string;
  title: React.ReactNode;
  render?: (record: T, index: number) => React.ReactNode;
  className?: string;
  /** Enable click-to-sort on this column's header. */
  sortable?: boolean;
  /** Custom sort key (e.g. a numeric value behind a formatted cell). */
  sortAccessor?: (record: T) => string | number | null | undefined;
  /** Cell/header text alignment. */
  align?: 'left' | 'center' | 'right';
  /** Offer this column in the column-visibility menu (default: true when the
   *  feature is enabled). Set false to pin it always-visible. */
  hideable?: boolean;
  /** Start hidden (still toggleable in the menu). */
  defaultHidden?: boolean;
  /** Label in the column-visibility menu + CSV header; falls back to `title`. */
  menuLabel?: string;
  /** Value emitted for CSV export (falls back to the raw `key` value). */
  exportValue?: (record: T) => string | number | null | undefined;
}

/** Server-side pagination descriptor. Absent → the built-in client pagination. */
export interface DataTablePagination {
  mode: 'client' | 'server';
  /** 1-based current page. */
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export interface DataTableFilterChip {
  id: string;
  label: string;
  onRemove: () => void;
}

/** A single sort directive: the column `key` plus its direction. */
export interface DataTableSort {
  key: string;
  desc: boolean;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  loading?: boolean;
  searchable?: boolean;
  searchPlaceholder?: string;
  pageSize?: number;
  emptyMessage?: string;
  getRowKey?: (record: T, index: number) => string | number;
  onRowClick?: (record: T) => void;
  // --- additive (all optional, default off) ---
  /** Server pagination; when `mode: 'server'` the table renders `data` as-is. */
  pagination?: DataTablePagination;
  /** Controlled search value (server search); pairs with `onSearchChange`. */
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  /** Show a "Columns" menu to toggle column visibility. */
  enableColumnVisibility?: boolean;
  /** Show a CSV export button. */
  enableExport?: boolean;
  exportFilename?: string;
  /** Extra toolbar controls (e.g. a Create button), right-aligned. */
  toolbarActions?: React.ReactNode;
  /** Active filter chips (display + remove; the editor lives at the call site). */
  filterChips?: DataTableFilterChip[];
  /** When provided, rows render as cards below the `md` breakpoint. */
  renderCard?: (record: T, index: number) => React.ReactNode;
  /** Controlled sort state; pairs with `onSortChange`. */
  sort?: DataTableSort | null;
  /**
   * Take over sorting. Header clicks call this instead of re-ordering `data`,
   * and the rows render exactly as given — which is the only correct behaviour
   * under server pagination, where sorting client-side would shuffle the
   * current page rather than re-query the table.
   */
  onSortChange?: (sort: DataTableSort | null) => void;
}

function alignClass(align?: 'left' | 'center' | 'right'): string | undefined {
  if (align === 'right') return 'text-right';
  if (align === 'center') return 'text-center';
  return undefined;
}

interface ColumnMeta {
  className?: string;
}

/**
 * Generic table — client search + pagination + custom column rendering, with
 * opt-in sorting, column visibility, server pagination, a toolbar, filter chips
 * and a responsive card layout. Built on `@tanstack/react-table` + the shadcn
 * `Table` primitives. Backward-compatible with the legacy `bloom-ui/DataTable`.
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
  pagination,
  searchValue,
  onSearchChange,
  enableColumnVisibility = false,
  enableExport = false,
  exportFilename,
  toolbarActions,
  filterChips,
  renderCard,
  sort,
  onSortChange,
}: DataTableProps<T>) {
  const [globalFilter, setGlobalFilter] = useState('');
  const [localSorting, setLocalSorting] = useState<SortingState>([]);
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(() =>
    Object.fromEntries(columns.filter((c) => c.defaultHidden).map((c) => [c.key, false])),
  );
  const isDesktop = useIsDesktop();
  const serverMode = pagination?.mode === 'server';
  const controlledSearch = onSearchChange !== undefined;
  const controlledSort = onSortChange !== undefined;

  const sorting: SortingState = controlledSort
    ? sort
      ? [{ id: sort.key, desc: sort.desc }]
      : []
    : localSorting;

  const handleSortingChange = (updater: SortingState | ((s: SortingState) => SortingState)) => {
    const next = typeof updater === 'function' ? updater(sorting) : updater;
    if (!controlledSort) {
      setLocalSorting(next);
      return;
    }
    const [first] = next;
    onSortChange(first ? { key: first.id, desc: first.desc } : null);
  };

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
        enableSorting: !!col.sortable,
        enableHiding: col.hideable !== false,
        sortingFn: col.sortAccessor
          ? (a, b) => {
              const av = col.sortAccessor!(a.original);
              const bv = col.sortAccessor!(b.original);
              if (av == null && bv == null) return 0;
              if (av == null) return -1;
              if (bv == null) return 1;
              if (typeof av === 'number' && typeof bv === 'number') return av - bv;
              return String(av).localeCompare(String(bv));
            }
          : 'auto',
        meta: { className: cn(col.className, alignClass(col.align)) } satisfies ColumnMeta,
      })),
    [columns],
  );

  const table = useReactTable({
    data,
    columns: columnDefs,
    state: { globalFilter, sorting, columnVisibility },
    onGlobalFilterChange: setGlobalFilter,
    onSortingChange: handleSortingChange,
    onColumnVisibilityChange: setColumnVisibility,
    manualSorting: controlledSort,
    // Controlled sorting drives a server ORDER BY, where "unsorted" is not a
    // state the caller can render — dropping it makes the header a plain
    // asc/desc toggle instead of a three-click cycle whose middle step looks
    // like nothing happened.
    enableSortingRemoval: !controlledSort,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    ...(serverMode
      ? {
          manualPagination: true,
          pageCount: Math.max(1, Math.ceil(pagination.total / pagination.pageSize)),
        }
      : { getPaginationRowModel: getPaginationRowModel() }),
    initialState: { pagination: { pageSize: serverMode ? pagination!.pageSize : pageSize } },
    getRowId: getRowKey ? (row, index) => String(getRowKey(row, index)) : undefined,
  });

  if (loading) {
    return <Skeleton className="h-40 w-full" />;
  }

  const rows = table.getRowModel().rows;
  const clientPageCount = table.getPageCount();
  const visibleColCount = table.getVisibleLeafColumns().length;

  const handleExport = () => {
    const visibleCols = columns.filter((c) => table.getColumn(c.key)?.getIsVisible() !== false);
    const headers = visibleCols.map(
      (c) => c.menuLabel ?? (typeof c.title === 'string' ? c.title : c.key),
    );
    const exportRows = table.getSortedRowModel().rows.map((r) =>
      visibleCols.map((c) => {
        if (c.exportValue) return c.exportValue(r.original) ?? '';
        const v = (r.original as Record<string, unknown>)[c.key];
        return (v ?? '') as string | number;
      }),
    );
    downloadCSV(exportFilename ?? 'export.csv', toCSV(headers, exportRows));
  };

  const hideableColumns = columns.filter((c) => c.hideable !== false);
  const showToolbar =
    searchable || enableColumnVisibility || enableExport || toolbarActions != null;

  return (
    <div className="space-y-3">
      {showToolbar && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          {searchable ? (
            <div className="relative max-w-xs flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={controlledSearch ? (searchValue ?? '') : globalFilter}
                onChange={(e) =>
                  controlledSearch
                    ? onSearchChange(e.target.value)
                    : setGlobalFilter(e.target.value)
                }
                placeholder={searchPlaceholder}
                className="pl-8"
              />
            </div>
          ) : (
            <span />
          )}

          <div className="flex items-center gap-2">
            {enableColumnVisibility && hideableColumns.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="gap-1.5">
                    <SlidersHorizontal className="h-4 w-4" />
                    <span className="hidden sm:inline">Columns</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-44">
                  <DropdownMenuLabel>Columns</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  {hideableColumns.map((c) => {
                    const column = table.getColumn(c.key);
                    if (!column) return null;
                    return (
                      <DropdownMenuCheckboxItem
                        key={c.key}
                        checked={column.getIsVisible()}
                        onCheckedChange={(v) => column.toggleVisibility(!!v)}
                        onSelect={(e) => e.preventDefault()}
                      >
                        {c.menuLabel ?? (typeof c.title === 'string' ? c.title : c.key)}
                      </DropdownMenuCheckboxItem>
                    );
                  })}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
            {enableExport && (
              <Button variant="outline" size="sm" className="gap-1.5" onClick={handleExport}>
                <Download className="h-4 w-4" />
                <span className="hidden sm:inline">CSV</span>
              </Button>
            )}
            {toolbarActions}
          </div>
        </div>
      )}

      {filterChips && filterChips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {filterChips.map((chip) => (
            <span
              key={chip.id}
              className="inline-flex items-center gap-1 rounded-md border border-primary/30 bg-primary/5 px-2 py-1 text-xs text-primary"
            >
              <span className="truncate max-w-[12rem]">{chip.label}</span>
              <button
                type="button"
                onClick={chip.onRemove}
                className="hover:text-destructive"
                aria-label="remove"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {renderCard && !isDesktop ? (
        <div className="flex flex-col gap-2">
          {rows.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">{emptyMessage}</div>
          ) : (
            rows.map((row) => (
              <div
                key={row.id}
                onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                className={cn(onRowClick && 'cursor-pointer')}
              >
                {renderCard(row.original, row.index)}
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="rounded-md border border-border">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((hg) => (
                <TableRow key={hg.id} className="border-t-0">
                  {hg.headers.map((header) => {
                    const metaClass = (header.column.columnDef.meta as ColumnMeta)?.className;
                    return (
                      <TableHead key={header.id} className={metaClass}>
                        {header.isPlaceholder ? null : header.column.getCanSort() ? (
                          <button
                            type="button"
                            onClick={header.column.getToggleSortingHandler()}
                            className="inline-flex items-center gap-1 select-none hover:text-foreground cursor-pointer"
                          >
                            {flexRender(header.column.columnDef.header, header.getContext())}
                            {header.column.getIsSorted() === 'asc' ? (
                              <ChevronUp className="h-3.5 w-3.5" />
                            ) : header.column.getIsSorted() === 'desc' ? (
                              <ChevronDown className="h-3.5 w-3.5" />
                            ) : (
                              <ChevronsUpDown className="h-3.5 w-3.5 opacity-50" />
                            )}
                          </button>
                        ) : (
                          flexRender(header.column.columnDef.header, header.getContext())
                        )}
                      </TableHead>
                    );
                  })}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={visibleColCount || columns.length}
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
                        className={(cell.column.columnDef.meta as ColumnMeta)?.className}
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
      )}

      {serverMode ? (
        <ServerPager pagination={pagination} />
      ) : (
        clientPageCount > 1 && (
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {table.getState().pagination.pageIndex + 1} / {clientPageCount}
            </span>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="icon-sm"
                onClick={() => table.previousPage()}
                disabled={!table.getCanPreviousPage()}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon-sm"
                onClick={() => table.nextPage()}
                disabled={!table.getCanNextPage()}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )
      )}
    </div>
  );
}

function ServerPager({ pagination }: { pagination: DataTablePagination }) {
  const { page, pageSize, total, onPageChange } = pagination;
  if (total <= pageSize) return null;
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return (
    <div className="flex items-center justify-between text-sm text-muted-foreground">
      <span>
        {start}-{end} / {total}
      </span>
      <div className="flex gap-1">
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page * pageSize >= total}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
