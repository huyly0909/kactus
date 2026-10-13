import { Bug } from 'lucide-react';

import { cn } from '@/lib/utils';

/**
 * DebugMark — the debug-only FLAG marker: a yellow (`text-debug`) inline Bug icon,
 * echoing the global debug toggle in TopHeader. It flags an element (action button,
 * debug-only column) that renders only in debug mode; the call site still owns the
 * `{debugMode && …}` gate — this is only the visual. Inline by default (sits next
 * to the label/title it marks); pass `className` to resize or reposition.
 */
export function DebugMark({ className }: { className?: string }) {
  return (
    <Bug
      aria-hidden
      className={cn('inline-block size-3.5 shrink-0 align-middle text-debug', className)}
    />
  );
}
