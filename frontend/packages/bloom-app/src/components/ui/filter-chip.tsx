// FilterChipShell — the filter-chip pill shared by DataTable and ReportView (so
// the chip chrome can't drift between them). A bordered h-7 pill
// [ label · summary-badge ][ X ] that opens a popover with a bold field-label
// header + the editor passed as children.
//
// Presentational: it owns the pill chrome, the popover, the clear (X) button,
// and the open state. The caller supplies label / summary / active + the editor.

import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { X } from 'lucide-react';

import { cn } from '@/lib/utils';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

export interface FilterChipShellProps {
  label: string;
  /** Compact value summary shown as a badge; omit/empty → no badge. */
  summary?: string;
  /** A value is set → highlight the pill + show the clear (X) button. */
  active: boolean;
  onClear: () => void;
  /** Open the popover on mount (auto-focus a freshly-added chip). */
  defaultOpen?: boolean;
  /** Let the popover size to content (date calendar) instead of the w-72 cap. */
  wide?: boolean;
  /** The editor widget. */
  children: ReactNode;
}

export function FilterChipShell({
  label,
  summary,
  active,
  onClear,
  defaultOpen,
  wide,
  children,
}: FilterChipShellProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultOpen ?? false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <div
        className={cn(
          'inline-flex items-stretch h-7 pointer-coarse:h-9 rounded-md border text-xs overflow-hidden max-w-[16.25rem]',
          active
            ? 'border-primary/30 bg-primary/5 text-primary hover:bg-primary/10'
            : 'border-border bg-card text-muted-foreground hover:bg-accent hover:text-foreground',
        )}
      >
        <PopoverTrigger asChild>
          <button type="button" className="flex items-center gap-1.5 px-2 min-w-0 cursor-pointer">
            <span className={cn('shrink-0 truncate', active && 'font-medium')}>{label}</span>
            {active && summary && (
              <span className="inline-flex items-center h-4 px-1 rounded-sm bg-primary/15 text-[10px] font-semibold leading-none shrink-0 max-w-[7.5rem] truncate">
                {summary}
              </span>
            )}
          </button>
        </PopoverTrigger>
        {active && (
          <button
            type="button"
            aria-label={t('common.remove')}
            onClick={onClear}
            className="flex items-center px-1 pointer-coarse:px-2 border-l border-primary/20 hover:bg-destructive/10 hover:text-destructive cursor-pointer"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
      <PopoverContent align="start" className={cn('p-3', wide ? 'w-auto' : 'w-72')}>
        <div className="mb-2 text-xs font-semibold text-foreground/80">{label}</div>
        {children}
      </PopoverContent>
    </Popover>
  );
}
