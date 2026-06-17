import { useTranslation } from 'react-i18next';
import { Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { AssetType, MarketQuote, PortfolioItem } from '@/types/portfolio';

interface Props {
  items: PortfolioItem[];
  quotes: MarketQuote[];
  onRemove: (item: PortfolioItem) => void;
}

function num(v?: string | null): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

function fmt(v: number | null): string {
  return v == null ? '—' : v.toLocaleString();
}

export function QuotesTable({ items, quotes, onRemove }: Props) {
  const { t } = useTranslation();
  const byKey = new Map<string, MarketQuote>();
  for (const q of quotes) byKey.set(`${q.asset_type}:${q.code}`, q);

  if (items.length === 0) {
    return <p className="py-8 text-center text-sm text-muted-foreground">{t('portfolio.empty')}</p>;
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
          <tr>
            <th className="px-4 py-2 font-medium">{t('portfolio.col.code')}</th>
            <th className="px-4 py-2 font-medium">{t('portfolio.col.type')}</th>
            <th className="px-4 py-2 text-right font-medium">{t('portfolio.col.price')}</th>
            <th className="px-4 py-2 text-right font-medium">{t('portfolio.col.change')}</th>
            <th className="px-4 py-2 text-right font-medium">{t('portfolio.col.volume')}</th>
            <th className="px-4 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((item) => {
            const q = byKey.get(`${item.asset_type}:${item.code}`);
            const price = num(q?.match_price) ?? num(q?.sell_price);
            const ref = num(q?.ref_price);
            const change = price != null && ref != null && ref !== 0 ? price - ref : null;
            const pct = change != null && ref ? (change / ref) * 100 : null;
            const tone =
              change == null
                ? ''
                : change > 0
                  ? 'text-green-600'
                  : change < 0
                    ? 'text-red-600'
                    : '';
            return (
              <tr key={item.id} className="hover:bg-muted/30">
                <td className="px-4 py-2 font-semibold">{item.code}</td>
                <td className="px-4 py-2">
                  <Badge variant="secondary" className="text-[10px]">
                    {t(`portfolio.asset_type.${item.asset_type as AssetType}`)}
                  </Badge>
                </td>
                <td className="px-4 py-2 text-right tabular-nums">{fmt(price)}</td>
                <td className={cn('px-4 py-2 text-right tabular-nums', tone)}>
                  {change == null
                    ? '—'
                    : `${change > 0 ? '+' : ''}${change.toFixed(2)} (${pct?.toFixed(2)}%)`}
                </td>
                <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                  {fmt(num(q?.volume))}
                </td>
                <td className="px-4 py-2 text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    onClick={() => onRemove(item)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
