import { type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { fmtGold, num } from '@/lib/format';
import { UNIT_USD_PER_OZ, type GoldHistoryPoint } from '@/types/market';

interface GoldHistoryTableProps {
  points: GoldHistoryPoint[];
  /** `VND/luong` (domestic → buy/sell) or `USD/oz` (world → OHLC). Also drives
   * the number format (`fmtGold`). */
  unit: string;
}

type PriceKey = 'buy_price' | 'sell_price' | 'open' | 'high' | 'low' | 'close';

/**
 * Raw gold history as a paginated table (50/page) — the Chart↔Table toggle's
 * table view. Columns follow the unit: domestic series show buy/sell, world
 * gold (XAU) shows OHLC. Prices stay strings end to end (Decimal precision);
 * only the sort key parses to a number.
 */
export const GoldHistoryTable: FC<GoldHistoryTableProps> = ({ points, unit }) => {
  const { t } = useTranslation();
  const isWorld = unit === UNIT_USD_PER_OZ;

  const priceCol = (key: PriceKey, title: string): DataTableColumn<GoldHistoryPoint> => ({
    key,
    title,
    align: 'right',
    className: 'tabular-nums',
    sortable: true,
    sortAccessor: (r) => num(r[key]),
    render: (r) => fmtGold(r[key], unit),
  });

  const columns: DataTableColumn<GoldHistoryPoint>[] = [
    {
      key: 'date',
      title: t('market.gold.history.date'),
      className: 'tabular-nums',
      sortable: true,
      sortAccessor: (r) => r.date,
      render: (r) => r.date,
    },
    ...(isWorld
      ? [
          priceCol('open', t('market.gold.history.open')),
          priceCol('high', t('market.gold.history.high')),
          priceCol('low', t('market.gold.history.low')),
          priceCol('close', t('market.gold.history.close')),
        ]
      : [
          priceCol('buy_price', t('market.gold.buy')),
          priceCol('sell_price', t('market.gold.sell')),
        ]),
  ];

  return (
    <DataTable
      columns={columns}
      data={points}
      pageSize={50}
      searchable={false}
      enableExport
      exportFilename={`gold-history-${isWorld ? 'xau' : 'vnd'}.csv`}
      getRowKey={(r) => `${r.source ?? ''}:${r.date}`}
      emptyMessage={t('market.gold.history.empty')}
    />
  );
};
