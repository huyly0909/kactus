import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  [
    'group/button inline-flex shrink-0 cursor-pointer select-none items-center justify-center',
    'whitespace-nowrap rounded-md border border-transparent text-sm font-medium shadow-sm',
    'outline-none transition-all duration-150 ease-in-out active:scale-[0.98]',
    // 3px ring — a button is an action, so its focus ring is louder than the
    // 1px ring on Input/SelectTrigger.
    'focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50',
    'aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20',
    'disabled:pointer-events-none disabled:opacity-50',
    // `:not([class*='h-'])` as well as `size-`: kactus icons are written
    // `h-4 w-4`, never `size-4`, so the size- guard alone would force every
    // deliberately-smaller `h-3.5` icon back up to 16px.
    "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-']):not([class*='h-'])]:size-4",
  ],
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        // Stays solid, unlike buitiful's tinted one: `confirm-dialog.tsx` uses
        // `destructive` as the primary CTA of every destroy flow, and a tint
        // demotes it to a secondary action.
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        // ...the tinted one lives here instead, for icon-only remove/delete
        // triggers in tables and toolbars.
        'ghost-destructive':
          'text-destructive shadow-none hover:bg-destructive/10 hover:text-destructive dark:hover:bg-destructive/20',
        outline:
          'border-input bg-background hover:bg-accent hover:text-accent-foreground aria-expanded:bg-accent aria-expanded:text-accent-foreground',
        secondary:
          'bg-secondary text-secondary-foreground hover:bg-secondary/80 aria-expanded:bg-secondary',
        ghost:
          'shadow-none hover:bg-accent hover:text-accent-foreground aria-expanded:bg-accent aria-expanded:text-accent-foreground',
        success:
          'bg-success/15 text-success shadow-none hover:bg-success/25 focus-visible:border-success/40 focus-visible:ring-success/20',
        warning:
          'bg-warning/15 text-warning shadow-none hover:bg-warning/25 focus-visible:border-warning/40 focus-visible:ring-warning/20',
        link: 'text-primary underline-offset-4 shadow-none hover:underline',
      },
      // `pointer-coarse:` steps every size up on touch-primary devices so taps
      // land on a ≥40px target while desktops keep the compact heights. One
      // seam for the whole app — do NOT re-bump at call sites: an unprefixed
      // `h-*` in `className` cannot cancel a `pointer-coarse:` height.
      size: {
        default: 'h-8 gap-1.5 px-3 pointer-coarse:h-10',
        xs: "h-6 gap-1 px-2 text-xs pointer-coarse:h-8 [&_svg:not([class*='size-']):not([class*='h-'])]:size-3",
        sm: "h-7 gap-1 px-2.5 text-[0.8rem] pointer-coarse:h-9 [&_svg:not([class*='size-']):not([class*='h-'])]:size-3.5",
        lg: 'h-9 gap-1.5 px-4 pointer-coarse:h-10',
        icon: 'size-8 pointer-coarse:size-10',
        'icon-xs':
          "size-6 pointer-coarse:size-8 [&_svg:not([class*='size-']):not([class*='h-'])]:size-3",
        'icon-sm':
          "size-7 pointer-coarse:size-9 [&_svg:not([class*='size-']):not([class*='h-'])]:size-3.5",
        'icon-lg': 'size-9 pointer-coarse:size-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    // Default to type="button": a native <button> is type="submit", so a
    // toolbar action inside an EntityPage form would submit it on click. Real
    // submit buttons pass type="submit" explicitly. `asChild` forwards to a
    // child that owns its own semantics, so only stamp the native element.
    return (
      <Comp
        ref={ref}
        data-slot="button"
        type={asChild ? type : (type ?? 'button')}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';

export { Button, buttonVariants };
