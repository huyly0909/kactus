// DataTableFilterBar — the filter row that sits above a DataTable.
//
// Declarative: a page describes its filters as data (`TableFilterDef[]`) and
// hands over the current values; the bar renders each one as a FilterChipShell
// pill whose popover holds the editor. That is deliberately ONE control per
// filter, not the older "a bare <Select> row plus a second row of read-only
// chips echoing it" — the echo could drift from the control, and two rows of
// chrome for one concept is a lot of vertical space above a table.
//
// Values are a plain `Record<id, string | DateRange>`, which is exactly the
// shape `useTableQueryState` keeps, so the two compose without adapters.

import { type FC, type ReactNode } from 'react';

import { FilterChipShell } from '@/components/ui/filter-chip';
import {
  DateRangeCalendar,
  type DateRange,
  type DateRangePreset,
} from '@/components/ui/date-range-picker';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

export interface TableFilterOption {
  value: string;
  label: string;
}

export type TableFilterValue = string | DateRange;

export type TableFilterDef =
  | {
      id: string;
      kind: 'select';
      label: string;
      options: TableFilterOption[];
      /** The "no filter" option's value (default `'all'`) — never shown as active. */
      allValue?: string;
    }
  | {
      id: string;
      kind: 'dateRange';
      label: string;
      presets?: DateRangePreset[];
      /** Earliest selectable day ("YYYY-MM-DD"). */
      minDate?: string;
    };

export interface DataTableFilterBarProps {
  filters: TableFilterDef[];
  values: Record<string, TableFilterValue>;
  onChange: (id: string, value: TableFilterValue) => void;
  /** Right-aligned slot — status chips, refresh countdown, primary actions. */
  actions?: ReactNode;
  className?: string;
}

export const EMPTY_RANGE: DateRange = { from: '', to: '' };

/** Is this filter holding a value that actually narrows the result set? */
export function isFilterActive(def: TableFilterDef, value: TableFilterValue): boolean {
  if (def.kind === 'dateRange') {
    const r = (value as DateRange) ?? EMPTY_RANGE;
    return Boolean(r.from || r.to);
  }
  return Boolean(value) && value !== (def.allValue ?? 'all');
}

function summarize(def: TableFilterDef, value: TableFilterValue): string {
  if (def.kind === 'dateRange') {
    const r = (value as DateRange) ?? EMPTY_RANGE;
    return `${r.from || '…'} – ${r.to || '…'}`;
  }
  return def.options.find((o) => o.value === value)?.label ?? String(value ?? '');
}

export const DataTableFilterBar: FC<DataTableFilterBarProps> = ({
  filters,
  values,
  onChange,
  actions,
  className,
}) => {
  return (
    <div className={cn('flex flex-wrap items-center justify-between gap-2', className)}>
      <div className="flex flex-wrap items-center gap-1.5">
        {filters.map((def) => {
          const value = values[def.id];
          const active = isFilterActive(def, value);
          const clear = () =>
            onChange(def.id, def.kind === 'dateRange' ? EMPTY_RANGE : (def.allValue ?? 'all'));

          return (
            <FilterChipShell
              key={def.id}
              label={def.label}
              summary={active ? summarize(def, value) : undefined}
              active={active}
              onClear={clear}
              wide={def.kind === 'dateRange'}
            >
              {def.kind === 'select' ? (
                <Select
                  value={(value as string) ?? def.allValue ?? 'all'}
                  onValueChange={(v) => onChange(def.id, v)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {def.options.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <DateRangeCalendar
                  value={(value as DateRange) ?? EMPTY_RANGE}
                  onChange={(r) => onChange(def.id, r)}
                  presets={def.presets}
                  minDate={def.minDate}
                />
              )}
            </FilterChipShell>
          );
        })}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
};
