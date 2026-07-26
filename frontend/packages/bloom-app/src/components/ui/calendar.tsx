// Calendar — shadcn-style wrapper over react-day-picker v9, styled entirely
// with the app's Tailwind theme tokens (theme-bound radius, no external CSS).
// Ported from buitiful-core. Used by DateRangeCalendar (mode="range");
// single-date mode works too.
import { type ComponentProps } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { DayPicker, getDefaultClassNames } from 'react-day-picker';

import { cn } from '@/lib/utils';

export type CalendarProps = ComponentProps<typeof DayPicker>;

export function Calendar({
  className,
  classNames,
  showOutsideDays = true,
  ...props
}: CalendarProps) {
  const base = getDefaultClassNames();
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      weekStartsOn={1}
      className={cn('p-2', className)}
      classNames={{
        // `relative` scopes the absolutely-positioned `nav` to the calendar
        // column. Without it the nav anchors to the popover and the prev/next
        // chevrons fly out to the popover's left/right edges.
        months: cn(base.months, 'relative flex flex-col'),
        month: cn(base.month, 'space-y-3'),
        month_caption: cn(base.month_caption, 'relative flex h-8 items-center justify-center'),
        caption_label: cn(base.caption_label, 'text-sm font-semibold'),
        nav: cn(base.nav, 'absolute inset-x-0 top-0 flex h-8 items-center justify-between'),
        // Real buttons: bordered ghost with a clear chevron + hover, not a faint
        // floating glyph stuck to the edge.
        button_previous: cn(
          base.button_previous,
          'inline-flex size-7 items-center justify-center rounded-md border border-input bg-background text-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-40',
        ),
        button_next: cn(
          base.button_next,
          'inline-flex size-7 items-center justify-center rounded-md border border-input bg-background text-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-40',
        ),
        month_grid: cn(base.month_grid, 'w-full border-collapse'),
        weekdays: cn(base.weekdays, 'flex'),
        weekday: cn(base.weekday, 'w-8 pb-1 text-xs font-normal text-muted-foreground'),
        week: cn(base.week, 'mt-1 flex w-full'),
        day: cn(base.day, 'relative size-8 p-0 text-center text-sm'),
        day_button: cn(
          base.day_button,
          'inline-flex size-8 cursor-pointer items-center justify-center rounded-md text-sm text-foreground transition-colors hover:bg-accent hover:text-accent-foreground',
        ),
        // Selected = every day in a range AND a single pick. Solid fill with a
        // foreground that contrasts in EVERY theme. The hover override stops
        // day_button's hover:bg-accent from stealing the fill mid-interaction.
        selected: cn(
          base.selected,
          '[&>button]:bg-primary [&>button]:text-primary-foreground',
          '[&>button]:hover:bg-primary [&>button]:hover:text-primary-foreground',
        ),
        // Today = ring + weight only, NEVER a text color. A text color here
        // collides with `selected`'s text-primary-foreground and vanishes when
        // today is the selected day in a light-`--primary` theme.
        today: cn(
          base.today,
          '[&>button]:font-semibold [&>button]:ring-1 [&>button]:ring-inset [&>button]:ring-primary/60',
        ),
        outside: cn(base.outside, 'text-muted-foreground/40'),
        disabled: cn(base.disabled, 'opacity-40'),
        hidden: cn(base.hidden, 'invisible'),
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation }) =>
          orientation === 'left' ? (
            <ChevronLeft className="size-4" />
          ) : (
            <ChevronRight className="size-4" />
          ),
      }}
      {...props}
    />
  );
}
