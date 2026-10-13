// useTableQueryState — page + sort + filters for a server-paginated DataTable.
//
// Every server-paged surface needs the same three pieces of state and the same
// two rules about how they interact:
//
//   1. Changing a filter or the sort resets the page to 1. Otherwise a user
//      filtering from page 4 lands on an empty page and reads it as "no
//      results" — the classic and very confusing bug.
//   2. The state can mirror into the URL, so a filtered view survives a reload
//      and can be pasted to a colleague ("look at these failed jobs").
//
// Values are `string | DateRange`, the same union `DataTableFilterBar` renders,
// so the two compose without an adapter.

import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

import type { DataTableSort } from '@/components/ui/data-table';
import type { DateRange } from '@/components/ui/date-range-picker';
import type { TableFilterValue } from '@/components/ui/data-table-filters';

export type TableFilters = Record<string, TableFilterValue>;

export interface UseTableQueryStateOptions<F extends TableFilters> {
  defaultFilters: F;
  defaultSort?: DataTableSort | null;
  pageSize?: number;
  /**
   * Prefix for the URL params (`<urlKey>_page`, `<urlKey>_sort`, `<urlKey>_<id>`).
   * Omit to keep the state in the URL-less default — but note the state still
   * lives in `useSearchParams`, so a prefix is what keeps two tables on one
   * page from colliding.
   */
  urlKey: string;
}

export interface TableQueryState<F extends TableFilters> {
  page: number;
  setPage: (page: number) => void;
  pageSize: number;
  sort: DataTableSort | null;
  setSort: (sort: DataTableSort | null) => void;
  filters: F;
  setFilter: (id: string, value: TableFilterValue) => void;
  resetFilters: () => void;
  /** At least one filter differs from its default. */
  isFiltered: boolean;
}

/** URL value meaning "sorted by nothing", as opposed to "no sort param yet". */
const NONE_SORT = '-';

const isRange = (v: TableFilterValue): v is DateRange =>
  typeof v === 'object' && v !== null && 'from' in v;

/** `{from,to}` → `"from..to"` (and back) — one URL param per filter. */
function encode(value: TableFilterValue): string {
  return isRange(value) ? (value.from || value.to ? `${value.from}..${value.to}` : '') : value;
}

function decode(raw: string, fallback: TableFilterValue): TableFilterValue {
  if (!isRange(fallback)) return raw;
  const [from = '', to = ''] = raw.split('..');
  return { from, to };
}

function sameValue(a: TableFilterValue, b: TableFilterValue): boolean {
  return encode(a) === encode(b);
}

export function useTableQueryState<F extends TableFilters>({
  defaultFilters,
  defaultSort = null,
  pageSize = 20,
  urlKey,
}: UseTableQueryStateOptions<F>): TableQueryState<F> {
  const [params, setParams] = useSearchParams();
  const key = useCallback((name: string) => `${urlKey}_${name}`, [urlKey]);

  const page = Math.max(1, Number(params.get(key('page')) ?? 1) || 1);

  const sort = useMemo<DataTableSort | null>(() => {
    const raw = params.get(key('sort'));
    // Absent → the default. NONE_SORT → the user cleared it, which is a real
    // state and must not silently fall back to the default.
    if (raw === null) return defaultSort;
    if (raw === NONE_SORT) return null;
    const [id, dir] = raw.split(':');
    return id ? { key: id, desc: dir !== 'asc' } : null;
    // `defaultSort` is a literal at every call site; including it would churn
    // the memo on every render for no gain.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, key]);

  const filters = useMemo(() => {
    const out = { ...defaultFilters };
    for (const [id, fallback] of Object.entries(defaultFilters)) {
      const raw = params.get(key(id));
      if (raw !== null) (out as TableFilters)[id] = decode(raw, fallback);
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, key]);

  // One writer for every mutation: apply the patch, then reset the page unless
  // the patch *is* the page. Keeping rule 1 in a single place is the point.
  const patch = useCallback(
    (entries: Record<string, string>, { keepPage = false } = {}) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [name, value] of Object.entries(entries)) {
            if (value) next.set(key(name), value);
            else next.delete(key(name));
          }
          if (!keepPage) next.delete(key('page'));
          return next;
        },
        { replace: true },
      );
    },
    [setParams, key],
  );

  const setPage = useCallback(
    (next: number) => patch({ page: next > 1 ? String(next) : '' }, { keepPage: true }),
    [patch],
  );

  const setSort = useCallback(
    (next: DataTableSort | null) =>
      patch({ sort: next ? `${next.key}:${next.desc ? 'desc' : 'asc'}` : NONE_SORT }),
    [patch],
  );

  const setFilter = useCallback(
    (id: string, value: TableFilterValue) => {
      const fallback = defaultFilters[id];
      patch({ [id]: sameValue(value, fallback) ? '' : encode(value) });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [patch],
  );

  const resetFilters = useCallback(
    () => patch(Object.fromEntries(Object.keys(defaultFilters).map((id) => [id, '']))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [patch],
  );

  const isFiltered = Object.entries(defaultFilters).some(
    ([id, fallback]) => !sameValue(filters[id], fallback),
  );

  return {
    page,
    setPage,
    pageSize,
    sort,
    setSort,
    filters,
    setFilter,
    resetFilters,
    isFiltered,
  };
}
