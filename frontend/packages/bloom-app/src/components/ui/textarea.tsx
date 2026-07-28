import * as React from 'react';
import { cn } from '@/lib/utils';

/** Same shape as `Input`, minus the fixed height — see the note in `input.tsx`. */
const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        'flex min-h-16 w-full rounded-md border border-input bg-transparent px-2.5 py-2 text-base outline-none transition-all duration-150 md:text-sm',
        'placeholder:text-muted-foreground',
        'focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/30',
        'aria-invalid:border-destructive aria-invalid:ring-1 aria-invalid:ring-destructive/20',
        'disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      ref={ref}
      {...props}
    />
  );
});
Textarea.displayName = 'Textarea';

export { Textarea };
