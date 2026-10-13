import { type FC } from 'react';
import { cn } from '@/lib/utils';
import type { BadgeProps } from '@/components/ui/badge';
import type { SyncJobStatus } from '@/types/sync';

/** Map a job status to a Badge variant + the i18n key for its label. */
export function syncStatusBadge(status: SyncJobStatus): {
  variant: BadgeProps['variant'];
  labelKey: string;
} {
  switch (status) {
    case 'pending':
      return { variant: 'secondary', labelKey: 'market.sync.status.pending' };
    case 'running':
      return { variant: 'warning', labelKey: 'market.sync.status.running' };
    case 'success':
      return { variant: 'success', labelKey: 'market.sync.status.success' };
    case 'failed':
      return { variant: 'danger', labelKey: 'market.sync.status.failed' };
    case 'cancelled':
      return { variant: 'outline', labelKey: 'market.sync.status.cancelled' };
  }
}

interface SyncProgressBarProps {
  /** Whole-percent progress (0–100). */
  pct: number;
  /** Dim the fill for terminal/idle states (e.g. cancelled/failed). */
  muted?: boolean;
  className?: string;
}

/** A thin determinate progress bar — no shadcn `progress` primitive exists. */
export const SyncProgressBar: FC<SyncProgressBarProps> = ({ pct, muted, className }) => {
  const width = Math.max(0, Math.min(100, pct));
  return (
    <div
      className={cn('h-2 w-full overflow-hidden rounded-full bg-muted', className)}
      role="progressbar"
      aria-valuenow={width}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn(
          'h-full rounded-full transition-all duration-500',
          muted ? 'bg-muted-foreground/40' : 'bg-primary',
        )}
        style={{ width: `${width}%` }}
      />
    </div>
  );
};
