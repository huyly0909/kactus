import { type FC, type ReactNode } from 'react';
import { Info } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface FieldHintProps {
  /** The explanation itself — already translated. */
  children: ReactNode;
  side?: 'top' | 'right' | 'bottom' | 'left';
  className?: string;
}

/**
 * A small "?" mark beside a form label that reveals a format rule or constraint
 * on hover/focus. Use instead of a permanent grey sub-line when the rule only
 * matters while the field is being filled in — it keeps the form scannable.
 *
 *   <div className="flex items-center gap-1">
 *     <FormLabel>{t('projects.code')}</FormLabel>
 *     <FieldHint>{t('projects.code_format')}</FieldHint>
 *   </div>
 *
 * Render it as a **sibling** of `FormLabel`, never a child: `FormLabel` is a
 * Radix `Label`, so an icon nested inside it forwards clicks to the input.
 *
 * `TooltipProvider` is mounted once in `main.tsx`; the shadcn `Tooltip` here has
 * no `Portal`, so the content renders inline and would otherwise inherit the
 * label's colour and weight — hence the explicit `text-left font-normal`.
 */
export const FieldHint: FC<FieldHintProps> = ({ children, side = 'right', className }) => (
  <Tooltip>
    <TooltipTrigger asChild>
      <span
        // tabIndex so the rule is reachable without a pointer — Radix opens the
        // tooltip on focus, which is the only way a keyboard user sees it.
        tabIndex={0}
        className={cn(
          'inline-flex shrink-0 cursor-help items-center justify-center rounded-sm text-muted-foreground/60 transition-colors hover:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring',
          className,
        )}
      >
        <Info className="h-3.5 w-3.5" />
      </span>
    </TooltipTrigger>
    <TooltipContent side={side} align="start" className="max-w-xs text-left font-normal">
      {children}
    </TooltipContent>
  </Tooltip>
);
