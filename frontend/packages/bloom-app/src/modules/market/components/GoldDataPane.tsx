import { type FC, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { DownloadCloud, ListChecks, Loader2, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  useActiveSyncKeys,
  useEnqueueGoldBackfill,
  useEnqueueGoldSync,
  useSyncStream,
} from '@/hooks/useSyncQuery';
import { UNIT_USD_PER_OZ, UNIT_VND_PER_LUONG } from '@/types/market';
import { resolveGoldBackfillMin, todayLocal, type GoldSource } from '@/types/sync';
import { GoldSeriesPanel } from './GoldSeriesPanel';

const BACKFILL_ALL: { source: GoldSource; code?: string }[] = [
  { source: 'yahoo' },
  { source: 'sjc' },
  { source: 'mihong', code: '999' },
];

/**
 * Gold **Data** tab (superuser): one sub-tab per source (XAU / SJC / Mihong),
 * each with its history chart + backfill/sync controls, plus global
 * "backfill all" / "sync all" actions and a link to the shared sync queue.
 *
 * Mounts the SSE stream so a running job's progress updates live on the
 * `redis` backend; the per-query poll covers the `memory` backend.
 */
export const GoldDataPane: FC = () => {
  const { t } = useTranslation();
  const [sub, setSub] = useState('xau');
  const enqueueBackfill = useEnqueueGoldBackfill();
  const enqueueSync = useEnqueueGoldSync();
  const activeKeys = useActiveSyncKeys();
  useSyncStream();

  const backfillAll = async () => {
    let queued = 0;
    for (const { source, code } of BACKFILL_ALL) {
      try {
        const res = await enqueueBackfill.mutateAsync({
          source,
          code,
          date_from: resolveGoldBackfillMin(source),
          date_to: todayLocal(),
        });
        if (res.created) queued += 1;
      } catch {
        /* keep going — one source failing must not abort the rest */
      }
    }
    toast.success(t('market.sync.backfill_all_queued', { count: queued }));
  };

  const syncAll = async () => {
    try {
      const res = await enqueueSync.mutateAsync({ source: 'all' });
      toast.success(res.created ? t('market.sync.queued') : t('market.sync.already_queued'));
    } catch {
      toast.error(t('market.sync.enqueue_failed'));
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">{t('market.sync.data_hint')}</p>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={backfillAll}
            disabled={enqueueBackfill.isPending}
          >
            {enqueueBackfill.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <DownloadCloud className="h-4 w-4" />
            )}
            {t('market.sync.backfill_all')}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={syncAll}
            disabled={enqueueSync.isPending || activeKeys.has('gold_sync:all')}
          >
            <RefreshCw className="h-4 w-4" />
            {t('market.sync.sync_all')}
          </Button>
          <Button size="sm" variant="ghost" asChild>
            <Link to="/market/sync">
              <ListChecks className="h-4 w-4" />
              {t('market.sync.view_queue')}
            </Link>
          </Button>
        </div>
      </div>

      <Tabs value={sub} onValueChange={setSub}>
        <TabsList>
          <TabsTrigger value="xau">{t('market.sync.source.yahoo')}</TabsTrigger>
          <TabsTrigger value="sjc">{t('market.sync.source.sjc')}</TabsTrigger>
          <TabsTrigger value="mihong">{t('market.sync.source.mihong')}</TabsTrigger>
        </TabsList>
        <TabsContent value="xau" className="pt-4">
          <GoldSeriesPanel code="XAU" source="yahoo" unit={UNIT_USD_PER_OZ} />
        </TabsContent>
        <TabsContent value="sjc" className="pt-4">
          <GoldSeriesPanel code="SJC" source="sjc" unit={UNIT_VND_PER_LUONG} />
        </TabsContent>
        <TabsContent value="mihong" className="pt-4">
          <GoldSeriesPanel
            code="999"
            source="mihong"
            backfillCode="999"
            unit={UNIT_VND_PER_LUONG}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
};
