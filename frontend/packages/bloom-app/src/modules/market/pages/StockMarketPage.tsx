import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { LineChart, Search } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { DataTable, type DataTableColumn } from '@/components/ui/data-table';
import { useStockQuotes, useStockSearch } from '@/hooks/useMarketQuery';
import { fmt, fmtChange, toneOf } from '@/lib/format';
import { cn } from '@/lib/utils';
import type { StockListing, StockQuote } from '@/types/market';

/** Listed-symbol catalogue with the latest board quote per symbol. */
export function StockMarketPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const { data: listings, isLoading } = useStockSearch(query);

  const symbols = useMemo(() => (listings ?? []).map((l) => l.symbol), [listings]);
  const { data: quoteRows } = useStockQuotes(symbols);
  const quotes = useMemo(
    () => new Map<string, StockQuote>((quoteRows ?? []).map((q) => [q.symbol, q])),
    [quoteRows],
  );

  const columns: DataTableColumn<StockListing>[] = [
    { key: 'symbol', title: t('market.stock.symbol'), className: 'font-semibold' },
    {
      key: 'organ_name',
      title: t('market.stock.company'),
      render: (s) => <span className="text-muted-foreground">{s.organ_name ?? '—'}</span>,
    },
    {
      key: 'price',
      title: t('market.stock.price'),
      className: 'text-right',
      render: (s) => <span className="tabular-nums">{fmt(quotes.get(s.symbol)?.match_price)}</span>,
    },
    {
      key: 'change',
      title: t('market.stock.change'),
      className: 'text-right',
      render: (s) => {
        const q = quotes.get(s.symbol);
        return (
          <span className={cn('tabular-nums', toneOf(q?.change))}>
            {fmtChange(q?.change, q?.change_pct)}
          </span>
        );
      },
    },
    {
      key: 'volume',
      title: t('market.stock.volume'),
      className: 'text-right',
      render: (s) => (
        <span className="tabular-nums text-muted-foreground">
          {fmt(quotes.get(s.symbol)?.accumulated_volume)}
        </span>
      ),
    },
    {
      key: 'source',
      title: t('market.source'),
      render: (s) => <Badge variant="outline">{s.source ?? '—'}</Badge>,
    },
  ];

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary">
          <LineChart className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('market.stock.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('market.stock.subtitle')}</p>
        </div>
      </div>

      {/* Server-side search — the catalogue is far larger than one page. */}
      <div className="relative mb-4 max-w-sm">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('market.stock.search_placeholder')}
          className="pl-8"
        />
      </div>

      <DataTable
        columns={columns}
        data={listings ?? []}
        loading={isLoading}
        searchable={false}
        emptyMessage={t('market.empty')}
        getRowKey={(s) => s.symbol}
        onRowClick={(s) => navigate(`/market/stocks/${s.symbol}`)}
      />
    </div>
  );
}
