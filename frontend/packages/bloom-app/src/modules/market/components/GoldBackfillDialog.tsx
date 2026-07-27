import { type FC, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Loader2, PlayCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DateRangeCalendar,
  datePresets,
  type DateRange,
  type DateRangePreset,
} from '@/components/ui/date-range-picker';
import { useEnqueueGoldBackfill } from '@/hooks/useSyncQuery';
import { resolveGoldBackfillMin, todayLocal, type GoldSource } from '@/types/sync';

interface GoldBackfillDialogProps {
  source: GoldSource;
  /** Domestic code override (Mihong 999); SJC/Yahoo ignore it. */
  code?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Configure + enqueue a gold-history backfill for one source.
 *
 * The date picker is bounded below at the source's earliest available day
 * (`min`), and the **All** preset resolves to that floor → today (rather than
 * the generic unbounded range) so a click can't ask for data the feed cannot
 * serve. The backend clamps again, defensively.
 */
export const GoldBackfillDialog: FC<GoldBackfillDialogProps> = ({
  source,
  code,
  open,
  onOpenChange,
}) => {
  const { t } = useTranslation();
  const enqueue = useEnqueueGoldBackfill();
  const min = useMemo(() => resolveGoldBackfillMin(source), [source]);

  const presets = useMemo<DateRangePreset[]>(
    () => [
      ...datePresets('today', '3d', '7d', '30d', '90d', '1y'),
      {
        key: 'all',
        labelKey: 'common.range_all',
        divider: true,
        range: (): DateRange => ({ from: min, to: todayLocal() }),
      },
    ],
    [min],
  );

  const [range, setRange] = useState<DateRange>(() => ({ from: min, to: todayLocal() }));

  const valid = Boolean(range.from && range.to && range.from <= range.to);

  const run = async () => {
    try {
      const res = await enqueue.mutateAsync({
        source,
        code,
        date_from: range.from,
        date_to: range.to,
      });
      toast.success(res.created ? t('market.sync.queued') : t('market.sync.already_queued'));
      onOpenChange(false);
    } catch {
      toast.error(t('market.sync.enqueue_failed'));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-fit">
        <DialogHeader>
          <DialogTitle>
            {t('market.sync.backfill_title', { source: t(`market.sync.source.${source}`) })}
          </DialogTitle>
          <DialogDescription>
            {t('market.sync.backfill_desc', { min })}
            {source === 'mihong' ? ` ${t('market.sync.mihong_note')}` : ''}
          </DialogDescription>
        </DialogHeader>

        <DateRangeCalendar value={range} onChange={setRange} presets={presets} minDate={min} />

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button onClick={run} disabled={!valid || enqueue.isPending}>
            {enqueue.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <PlayCircle className="h-4 w-4" />
            )}
            {t('market.sync.run')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
