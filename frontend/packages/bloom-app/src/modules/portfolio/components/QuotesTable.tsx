import { useTranslation } from 'react-i18next';
import { Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fmtGold } from '@/lib/format';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
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
    <div className="rounded-md border border-border">
      <Table>
        <TableHeader>
          <TableRow className="border-t-0">
            <TableHead>{t('portfolio.col.code')}</TableHead>
            <TableHead>{t('portfolio.col.type')}</TableHead>
            <TableHead className="text-right">{t('portfolio.col.price')}</TableHead>
            <TableHead className="text-right">{t('portfolio.col.change')}</TableHead>
            <TableHead className="text-right">{t('portfolio.col.volume')}</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
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
                  ? 'text-[var(--gain)]'
                  : change < 0
                    ? 'text-[var(--loss)]'
                    : '';
            return (
              <TableRow key={item.id}>
                <TableCell className="font-semibold">{item.code}</TableCell>
                <TableCell>
                  <Badge variant="secondary" className="text-[10px]">
                    {t(`portfolio.asset_type.${item.asset_type as AssetType}`)}
                  </Badge>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {q?.unit ? fmtGold(price, q.unit) : fmt(price)}
                  {q?.unit && (
                    <span className="ml-1 text-[10px] font-normal text-muted-foreground">
                      {q.unit}
                    </span>
                  )}
                </TableCell>
                <TableCell className={cn('text-right tabular-nums', tone)}>
                  {change == null
                    ? '—'
                    : `${change > 0 ? '+' : ''}${change.toFixed(2)} (${pct?.toFixed(2)}%)`}
                </TableCell>
                <TableCell className="text-right tabular-nums text-muted-foreground">
                  {fmt(num(q?.volume))}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    onClick={() => onRemove(item)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
