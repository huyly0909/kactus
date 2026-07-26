// Date-range widget — ported from buitiful-core. ONE shared primitive, three
// entry points:
//   • DateRangeCalendar — optional preset column + react-day-picker calendar +
//     native from/to inputs. Bare content; the caller owns the popover.
//   • DateRangePicker — a trigger button + popover wrapping DateRangeCalendar,
//     for self-contained callers.
//   • DateRangeControl — external quick-select chips + the DateRangePicker, for
//     dashboards/charts that want the ranges always visible.
//
// The quick selections are NOT hardcoded in the widget — each dashboard/chart
// passes exactly the presets it needs via the `presets` prop. Build that list
// with `datePresets('week', 'month', 'quarter', '1y', ...)` from the shared
// registry, or hand-roll `DateRangePreset[]`.
//
// Value is { from, to } as "YYYY-MM-DD" local-date strings ('' = unset; both ''
// means "no bounds", i.e. an all-time range).

import { type FC, Fragment, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Calendar as CalendarIcon } from 'lucide-react';
import type { DateRange as RdpRange } from 'react-day-picker';

import { Button } from '@/components/ui/button';
import { Calendar } from '@/components/ui/calendar';
import { Input } from '@/components/ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

export interface DateRange {
  /** "YYYY-MM-DD" or '' when unset. */
  from: string;
  to: string;
}

export interface DateRangePreset {
  /** Stable id, e.g. 'week', 'quarter', '1y', 'all'. */
  key: string;
  /** i18n key for the label, e.g. 'common.range_quarter'. */
  labelKey: string;
  /** Render a horizontal rule BEFORE this preset in the column. */
  divider?: boolean;
  /** Lazily compute { from, to } from "today" — recomputed on every click. */
  range: () => DateRange;
}

// "YYYY-MM-DD" from a local Date, built from parts so there's no UTC shift that
// could land the value on the previous day near midnight.
function fmt(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

// "2026-06-01" → local Date (or undefined), from parts (same no-UTC-shift reason).
function parse(s: string): Date | undefined {
  if (!s) return undefined;
  const [y, m, d] = s.split('-').map(Number);
  if (!y || !m || !d) return undefined;
  return new Date(y, m - 1, d);
}

function trailingYears(n: number): DateRange {
  const now = new Date();
  const from = new Date(now);
  from.setFullYear(from.getFullYear() - n);
  return { from: fmt(from), to: fmt(now) };
}

function trailingDays(n: number): DateRange {
  const now = new Date();
  const from = new Date(now);
  from.setDate(from.getDate() - (n - 1));
  return { from: fmt(from), to: fmt(now) };
}

// Shared preset registry. Each range() reads `new Date()` at click-time, so a
// preset stays correct across day boundaries without a rebuild. Labels live in
// the `common.range_*` i18n namespace (vi + en).
const REGISTRY: Record<string, DateRangePreset> = {
  today: {
    key: 'today',
    labelKey: 'common.range_today',
    range: () => {
      const t = fmt(new Date());
      return { from: t, to: t };
    },
  },
  yesterday: {
    key: 'yesterday',
    labelKey: 'common.range_yesterday',
    range: () => {
      const d = new Date();
      d.setDate(d.getDate() - 1);
      const t = fmt(d);
      return { from: t, to: t };
    },
  },
  week: {
    key: 'week',
    labelKey: 'common.range_week',
    range: () => {
      const now = new Date();
      const from = new Date(now);
      const day = from.getDay();
      from.setDate(from.getDate() - (day === 0 ? 6 : day - 1)); // Monday-anchored
      return { from: fmt(from), to: fmt(now) };
    },
  },
  month: {
    key: 'month',
    labelKey: 'common.range_month',
    range: () => {
      const now = new Date();
      return { from: fmt(new Date(now.getFullYear(), now.getMonth(), 1)), to: fmt(now) };
    },
  },
  last_month: {
    key: 'last_month',
    labelKey: 'common.range_last_month',
    range: () => {
      const now = new Date();
      return {
        from: fmt(new Date(now.getFullYear(), now.getMonth() - 1, 1)),
        to: fmt(new Date(now.getFullYear(), now.getMonth(), 0)),
      };
    },
  },
  quarter: {
    key: 'quarter',
    labelKey: 'common.range_quarter',
    range: () => {
      const now = new Date();
      const q = Math.floor(now.getMonth() / 3) * 3;
      return { from: fmt(new Date(now.getFullYear(), q, 1)), to: fmt(now) };
    },
  },
  year: {
    key: 'year',
    labelKey: 'common.range_year',
    range: () => {
      const now = new Date();
      return { from: fmt(new Date(now.getFullYear(), 0, 1)), to: fmt(now) };
    },
  },
  '1y': { key: '1y', labelKey: 'common.range_1y', divider: true, range: () => trailingYears(1) },
  '3y': { key: '3y', labelKey: 'common.range_3y', range: () => trailingYears(3) },
  '5y': { key: '5y', labelKey: 'common.range_5y', range: () => trailingYears(5) },
  '7d': { key: '7d', labelKey: 'common.range_7d', divider: true, range: () => trailingDays(7) },
  '30d': { key: '30d', labelKey: 'common.range_30d', range: () => trailingDays(30) },
  '90d': { key: '90d', labelKey: 'common.range_90d', range: () => trailingDays(90) },
  all: {
    key: 'all',
    labelKey: 'common.range_all',
    divider: true,
    range: () => ({ from: '', to: '' }),
  },
};

/**
 * Resolve a list of preset keys into ordered {@link DateRangePreset}s. Unknown
 * keys are dropped. This is how a chart declares its quick selections, e.g.
 * `datePresets('week', 'month', 'quarter', '1y', '3y', '5y', 'all')`.
 */
export function datePresets(...keys: string[]): DateRangePreset[] {
  return keys.map((k) => REGISTRY[k]).filter((p): p is DateRangePreset => Boolean(p));
}

function isActive(preset: DateRangePreset, value: DateRange): boolean {
  const r = preset.range();
  return r.from === value.from && r.to === value.to;
}

interface DateRangeCalendarProps {
  value: DateRange;
  onChange: (r: DateRange) => void;
  /** Quick-select presets shown as a left column. Omit for calendar-only. */
  presets?: DateRangePreset[];
}

/** Optional preset column + calendar + custom from/to inputs. No popover chrome. */
export const DateRangeCalendar: FC<DateRangeCalendarProps> = ({ value, onChange, presets }) => {
  const { t } = useTranslation();
  const selected: RdpRange | undefined =
    value.from || value.to ? { from: parse(value.from), to: parse(value.to) } : undefined;

  return (
    // Below sm the preset column stacks above the calendar as a wrap row —
    // side-by-side would push the popover past a narrow viewport.
    <div className="flex flex-col gap-2 sm:flex-row">
      {presets && presets.length > 0 && (
        <div className="flex w-full flex-row flex-wrap gap-1 sm:w-28 sm:shrink-0 sm:flex-col">
          {presets.map((p) => (
            <Fragment key={p.key}>
              {p.divider && (
                <div role="separator" aria-hidden className="hidden sm:block my-1 h-px bg-border" />
              )}
              <Button
                type="button"
                size="sm"
                variant={isActive(p, value) ? 'default' : 'outline'}
                className="justify-start sm:w-full"
                onClick={() => onChange(p.range())}
              >
                {t(p.labelKey)}
              </Button>
            </Fragment>
          ))}
        </div>
      )}
      <div className="flex flex-col gap-2">
        <Calendar
          mode="range"
          selected={selected}
          defaultMonth={parse(value.from) ?? parse(value.to)}
          onSelect={(r) =>
            onChange({ from: r?.from ? fmt(r.from) : '', to: r?.to ? fmt(r.to) : '' })
          }
        />
        <div className="flex items-center gap-1">
          <Input
            type="date"
            value={value.from}
            max={value.to || undefined}
            onChange={(e) => onChange({ ...value, from: e.target.value })}
            className="h-8 w-auto px-2 text-xs"
          />
          <span className="shrink-0 text-xs text-muted-foreground">–</span>
          <Input
            type="date"
            value={value.to}
            min={value.from || undefined}
            onChange={(e) => onChange({ ...value, to: e.target.value })}
            className="h-8 w-auto px-2 text-xs"
          />
        </div>
      </div>
    </div>
  );
};

interface DateRangePickerProps {
  value: DateRange;
  onChange: (r: DateRange) => void;
  /** Presets shown as the popover's left column. */
  presets?: DateRangePreset[];
  /** Trigger label when no range is set. Defaults to `common.range_pick`. */
  placeholder?: string;
  /** Highlight the trigger — e.g. when a custom range is the active selection. */
  active?: boolean;
  align?: 'start' | 'center' | 'end';
  className?: string;
}

/** Self-contained trigger button + popover wrapping {@link DateRangeCalendar}. */
export const DateRangePicker: FC<DateRangePickerProps> = ({
  value,
  onChange,
  presets,
  placeholder,
  active = false,
  align = 'end',
  className,
}) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const label =
    value.from || value.to
      ? `${value.from || '…'} – ${value.to || '…'}`
      : (placeholder ?? t('common.range_pick'));

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          size="sm"
          variant={active ? 'default' : 'outline'}
          className={cn('justify-start gap-1.5', className)}
        >
          <CalendarIcon className="h-4 w-4" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent align={align} className="w-auto p-3">
        <DateRangeCalendar value={value} onChange={onChange} presets={presets} />
      </PopoverContent>
    </Popover>
  );
};

interface DateRangeControlProps {
  value: DateRange;
  onChange: (r: DateRange) => void;
  /** The full preset set — surfaced as chips AND as the popover column. */
  presets: DateRangePreset[];
  /** Restrict the external chips to a subset of `presets` (by key). */
  quickKeys?: string[];
  /** Trigger label for the popover when no range is set. */
  placeholder?: string;
  className?: string;
}

/**
 * External quick-select chip row + the calendar popover. State is shared:
 * clicking a chip emits the same { from, to } as the popover, so the trigger
 * label and the in-popover preset highlight both reflect the choice.
 */
export const DateRangeControl: FC<DateRangeControlProps> = ({
  value,
  onChange,
  presets,
  quickKeys,
  placeholder,
  className,
}) => {
  const { t } = useTranslation();
  const chips = quickKeys
    ? quickKeys
        .map((k) => presets.find((p) => p.key === k))
        .filter((p): p is DateRangePreset => Boolean(p))
    : presets;
  // The trigger goes "active" when the current value is a custom range that no
  // preset produced.
  const custom = !presets.some((p) => isActive(p, value));

  return (
    <div className={cn('flex flex-wrap items-center gap-1', className)}>
      {chips.map((p) => (
        <Button
          key={p.key}
          type="button"
          size="sm"
          variant={isActive(p, value) ? 'default' : 'outline'}
          onClick={() => onChange(p.range())}
        >
          {t(p.labelKey)}
        </Button>
      ))}
      <DateRangePicker
        value={value}
        onChange={onChange}
        presets={presets}
        active={custom}
        placeholder={placeholder}
      />
    </div>
  );
};
