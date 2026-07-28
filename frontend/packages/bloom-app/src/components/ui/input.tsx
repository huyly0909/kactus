import * as React from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  /**
   * Rendered absolute-right inside the input border (a unit, a currency code, a
   * clear button). The field reserves `pr-12` for it, so keep it narrow.
   */
  suffix?: React.ReactNode;
  /**
   * `default` is the bordered form control; `inline` is a borderless underline
   * field for editing in place (inside a table cell, next to a label).
   */
  variant?: 'default' | 'inline';
}

/**
 * The control geometry shared by Input, Textarea and SelectTrigger: `h-8` with
 * `pointer-coarse:h-10` so a touch target still clears 40px. The focus ring is
 * 1px and quiet on purpose — a focused field says "you are here", it is not an
 * action like a Button (which rings 3px). Errors come from `aria-invalid`,
 * which `FormControl` already sets from the field state and which nothing
 * rendered before.
 *
 * Stays `bg-transparent`: both `Card` and `DialogContent` are `bg-card`, so a
 * filled input would disappear inside them.
 */
const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, suffix, variant = 'default', ...props }, ref) => {
    const control = (
      <input
        type={type}
        data-slot="input"
        className={cn(
          variant === 'inline'
            ? 'w-full min-w-0 border-b border-input bg-transparent px-1 py-0.5 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring aria-invalid:border-destructive disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50'
            : cn(
                'flex h-8 w-full min-w-0 rounded-md border border-input bg-transparent px-2.5 py-1 text-base outline-none transition-all duration-150 md:text-sm',
                'placeholder:text-muted-foreground',
                'file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground',
                'focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/30',
                'aria-invalid:border-destructive aria-invalid:ring-1 aria-invalid:ring-destructive/20',
                'disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50',
                'pointer-coarse:h-10',
              ),
          suffix && 'pr-12',
          className,
        )}
        ref={ref}
        {...props}
      />
    );

    if (!suffix) return control;
    return (
      <div className="relative w-full">
        {control}
        <div className="pointer-events-none absolute inset-y-0 right-2.5 flex items-center text-xs text-muted-foreground [&_button]:pointer-events-auto">
          {suffix}
        </div>
      </div>
    );
  },
);
Input.displayName = 'Input';

export { Input };
