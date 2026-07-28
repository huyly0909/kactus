import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden whitespace-nowrap rounded-md border border-transparent px-2 py-0.5 text-xs font-medium transition-all focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring/30 [&>svg]:pointer-events-none [&>svg]:size-3',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground',
        secondary: 'bg-secondary text-secondary-foreground',
        // Status pills are tinted, not solid — a badge reports state, it is not
        // an action. `dark:` here reads as "not inside .light", so the deeper
        // /20 tint is the default and `.light` gets the lighter /15.
        destructive: 'bg-destructive/15 text-destructive dark:bg-destructive/20',
        danger: 'bg-loss/15 text-loss dark:bg-loss/20',
        warning: 'bg-warning/15 text-warning dark:bg-warning/20',
        success: 'bg-success/15 text-success dark:bg-success/20',
        info: 'bg-info/15 text-info dark:bg-info/20',
        outline: 'border-border text-foreground',
        'primary-subtle': 'border-primary/20 bg-primary/10 text-primary',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {
  asChild?: boolean;
}

function Badge({ className, variant, asChild = false, ...props }: BadgeProps) {
  const Comp = asChild ? Slot : 'div';
  return (
    <Comp data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
