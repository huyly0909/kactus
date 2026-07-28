import { type FC, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface BareSectionProps {
  title?: ReactNode;
  /** Rendered on the same baseline as the title, pushed right (e.g. "+ Invite"). */
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

/**
 * Flat titled section for entity-detail pages: an uppercase underlined heading
 * followed by `FieldRow` children. Deliberately box-less — on a detail page the
 * page *is* the record, so wrapping each group in a Card adds a border that
 * separates nothing.
 */
export const BareSection: FC<BareSectionProps> = ({ title, action, children, className }) => (
  <div className={cn('space-y-1', className)}>
    {(title || action) && (
      <div className="flex items-center justify-between gap-2 border-b border-border pb-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
          {title}
        </h3>
        {action}
      </div>
    )}
    {children}
  </div>
);
