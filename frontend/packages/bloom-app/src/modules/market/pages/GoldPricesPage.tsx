import { useTranslation } from 'react-i18next';
import { Coins } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { useGoldPrices } from '@/hooks/useMarketQuery';
import { fmtGold, fmtDateTime } from '@/lib/format';
import { UNIT_USD_PER_OZ, type GoldPrice } from '@/types/market';

/**
 * Gold board — latest buy/sell quote per gold code.
 *
 * Rows are NOT all in the same unit: domestic codes (SJC, 999) are VND per
 * lượng while XAU is USD per troy ounce, so every row shows its unit and is
 * formatted accordingly.
 */
export function GoldPricesPage() {
  const { t } = useTranslation();
  const { data, isLoading } = useGoldPrices();

  const columns: DataTableColumn<GoldPrice>[] = [
    {
      key: 'code',
      title: t('market.gold.code'),
      className: 'font-semibold',
    },
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
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-[var(--warning)]/15 text-[var(--warning)]">
          <Coins className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('market.gold.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('market.gold.subtitle')}</p>
        </div>
      </div>

      <DataTable
        columns={columns}
        data={data ?? []}
        loading={isLoading}
        searchable
        searchPlaceholder={t('common.search')}
        emptyMessage={t('market.empty')}
        getRowKey={(g) => g.code}
      />
    </div>
  );
}
