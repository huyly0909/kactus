import { type FC, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Upload } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { useAuth } from '@/hooks/useAuth';
import { useFormatDateTime } from '@/hooks/useFormatDateTime';
import { useGoldPrices } from '@/hooks/useMarketQuery';
import { fmtGold } from '@/lib/format';
import { UNIT_USD_PER_OZ, type GoldPrice } from '@/types/market';
import { GoldHistoryCard } from './GoldHistoryCard';
import { GoldImportDialog } from './GoldImportDialog';

/**
 * Gold **Overview** tab — the latest board (one row per code) plus the history
 * chart. Rows are NOT all one unit: domestic codes (SJC, 999) are VND/lượng
 * while XAU is USD/oz, so every row shows its unit and formats accordingly.
 */
export const GoldOverviewPane: FC = () => {
  const { t } = useTranslation();
  const { data, isLoading } = useGoldPrices();
  const { user } = useAuth();
  const fmtDateTime = useFormatDateTime();
  const [importOpen, setImportOpen] = useState(false);

  const columns: DataTableColumn<GoldPrice>[] = [
    { key: 'code', title: t('market.gold.code'), className: 'font-semibold' },
    {
      key: 'buy_price',
      title: t('market.gold.buy'),
      className: 'text-right',
      render: (g) => <span className="tabular-nums">{fmtGold(g.buy_price, g.unit)}</span>,
    },
    {
      key: 'sell_price',
      title: t('market.gold.sell'),
      className: 'text-right',
      render: (g) => <span className="tabular-nums">{fmtGold(g.sell_price, g.unit)}</span>,
    },
    {
      key: 'spread',
      title: t('market.gold.spread'),
      className: 'text-right',
      render: (g) => (
        <span className="tabular-nums text-muted-foreground">{fmtGold(g.spread, g.unit)}</span>
      ),
    },
    {
      key: 'unit',
      title: t('market.gold.unit'),
      render: (g) => (
        <span className="text-xs text-muted-foreground">
          {g.unit === UNIT_USD_PER_OZ
            ? t('market.gold.unit_usd_oz')
            : t('market.gold.unit_vnd_luong')}
        </span>
      ),
    },
    {
      key: 'source',
      title: t('market.source'),
      render: (g) => <Badge variant="outline">{g.source ?? '—'}</Badge>,
    },
    {
      key: 'crawled_at',
      title: t('market.updated_at'),
      render: (g) => <span className="text-muted-foreground">{fmtDateTime(g.crawled_at)}</span>,
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      {user?.is_superuser && (
        <div className="flex justify-end">
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <Upload className="h-4 w-4" />
            {t('market.gold.import.button')}
          </Button>
        </div>
      )}

      <GoldHistoryCard />

      <DataTable
        columns={columns}
        data={data ?? []}
        loading={isLoading}
        searchable
        searchPlaceholder={t('common.search')}
        emptyMessage={t('market.empty')}
        getRowKey={(g) => g.code}
      />

      <GoldImportDialog open={importOpen} onOpenChange={setImportOpen} />
    </div>
  );
};
