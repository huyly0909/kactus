import { type FC, useEffect, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface RefreshCountdownProps {
  /** Called every `seconds` and on a manual click. */
  onRefresh: () => void;
  /** Seconds between auto-refreshes (default 5). */
  seconds?: number;
  /** Spin the icon while a refresh is in flight. */
  refreshing?: boolean;
  className?: string;
}

/**
 * A refresh button that also counts down and auto-fires `onRefresh` at zero,
 * then resets. Clicking refreshes immediately and restarts the count. Shared by
 * both Scheduler tabs so their cadence is identical.
 */
export const RefreshCountdown: FC<RefreshCountdownProps> = ({
  onRefresh,
  seconds = 5,
  refreshing = false,
  className,
}) => {
  const [remaining, setRemaining] = useState(seconds);
  // Keep the latest callback without restarting the interval each render.
  const cb = useRef(onRefresh);
  cb.current = onRefresh;

  // One 1s ticker for the lifetime of the component.
  useEffect(() => {
    const id = setInterval(() => setRemaining((r) => r - 1), 1000);
    return () => clearInterval(id);
  }, []);

  // Fire + reset when the count reaches zero (an update effect, so no
  // strict-mode double-fire, unlike a side effect inside the state updater).
  useEffect(() => {
    if (remaining <= 0) {
      cb.current();
      setRemaining(seconds);
    }
  }, [remaining, seconds]);

  const refreshNow = () => {
    cb.current();
    setRemaining(seconds);
  };

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={refreshNow}
      className={cn('gap-1.5 tabular-nums', className)}
    >
      <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
      <span className="text-xs text-muted-foreground">{Math.max(remaining, 0)}s</span>
    </Button>
  );
};
