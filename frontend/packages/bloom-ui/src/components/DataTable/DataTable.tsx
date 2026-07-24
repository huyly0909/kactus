import { type FC, useState } from 'react';
import { Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '../../lib/utils';

interface Column<T> {
  key: string;
  title: string;
  render?: (record: T, index: number) => React.ReactNode;
}

interface DataTableProps<T extends Record<string, unknown>> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  searchable?: boolean;
  searchPlaceholder?: string;
  pageSize?: number;
  title?: string;
  emptyMessage?: string;
}

/**
 * DataTable — table with search, pagination, and custom column rendering.
 * shadcn/Tailwind port (previously Mantine `Table`). Self-contained so the
 * package stays dependency-light; the app's `data-table` primitive mirrors this API.
 */
export const DataTable: FC<DataTableProps<Record<string, unknown>>> = ({
  columns,
  data,
  loading = false,
  searchable = true,
  searchPlaceholder = 'Search...',
  pageSize = 10,
  title,
  emptyMessage = 'No data found',
}) => {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const filteredData = search
    ? data.filter((row) =>
        Object.values(row).some((value) =>
          String(value).toLowerCase().includes(search.toLowerCase()),
        ),
      )
    : data;

  const totalPages = Math.ceil(filteredData.length / pageSize);
  const paginatedData = filteredData.slice((page - 1) * pageSize, page * pageSize);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4 text-card-foreground shadow-sm">
      {(title || searchable) && (
        <div className="mb-4 flex items-center justify-between gap-4">
          {title && <p className="text-lg font-semibold">{title}</p>}
          {searchable && (
            <div className="relative ml-auto w-full max-w-xs">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                className="flex h-9 w-full rounded-md border border-input bg-transparent pl-8 pr-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                placeholder={searchPlaceholder}
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
              />
            </div>
          )}
        </div>
      )}

      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
            <tr>
              {columns.map((col) => (
                <th key={col.key} className="px-3 py-2 font-medium">
                  {col.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedData.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="py-8 text-center text-muted-foreground">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              paginatedData.map((row, index) => (
                <tr key={index} className="border-t border-border hover:bg-muted/40">
                  {columns.map((col) => (
                    <td key={col.key} className="px-3 py-2">
                      {col.render ? col.render(row, index) : String(row[col.key] ?? '')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="mt-3 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {page} / {totalPages}
          </span>
          <div className="flex gap-1">
            <button
              className={cn(
                'inline-flex h-8 w-8 items-center justify-center rounded-md border border-input transition-colors hover:bg-accent disabled:pointer-events-none disabled:opacity-50',
              )}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              className={cn(
                'inline-flex h-8 w-8 items-center justify-center rounded-md border border-input transition-colors hover:bg-accent disabled:pointer-events-none disabled:opacity-50',
              )}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
