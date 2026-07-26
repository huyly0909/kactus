// A lean, dependency-free date-range control: a trigger button + popover with
// two native `type="date"` inputs. Value is `{ from, to }` as "YYYY-MM-DD"
// local-date strings ('' = unset). Kept native (no react-day-picker) to match
// the rest of the bloom-app UI, which ships no calendar primitive.
//
// Callers that also want quick-range chips render those themselves and pass
// `active` so the trigger reflects whether a custom range currently drives the
// view (see the gold history chart).

import { type FC, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Calendar as CalendarIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';

export interface DateRange {
  /** "YYYY-MM-DD" or '' when unset. */
  from: string;
  to: string;
}

interface DateRangePickerProps {
  value: DateRange;
  onChange: (r: DateRange) => void;
  /** Trigger label when no range is set. Defaults to `common.range_pick`. */
  placeholder?: string;
  /** Highlight the trigger — e.g. when a custom range is the active selection. */
  active?: boolean;
  className?: string;
}

export const DateRangePicker: FC<DateRangePickerProps> = ({
  value,
  onChange,
  placeholder,
  active = false,
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
      <PopoverContent align="end" className="w-auto p-3">
        <div className="flex flex-col gap-3">
          <div className="flex items-end gap-2">
            <div className="flex flex-col gap-1">
              <Label htmlFor="date-range-from" className="text-xs text-muted-foreground">
                {t('common.range_from')}
              </Label>
              <Input
                id="date-range-from"
                type="date"
                value={value.from}
                max={value.to || undefined}
                onChange={(e) => onChange({ ...value, from: e.target.value })}
                className="h-8 w-auto px-2 text-xs"
              />
            </div>
            <span className="pb-2 text-xs text-muted-foreground">–</span>
            <div className="flex flex-col gap-1">
              <Label htmlFor="date-range-to" className="text-xs text-muted-foreground">
                {t('common.range_to')}
              </Label>
              <Input
                id="date-range-to"
                type="date"
                value={value.to}
                min={value.from || undefined}
                onChange={(e) => onChange({ ...value, to: e.target.value })}
                className="h-8 w-auto px-2 text-xs"
              />
            </div>
          </div>
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={!value.from && !value.to}
              onClick={() => onChange({ from: '', to: '' })}
            >
              {t('common.range_clear')}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
};
