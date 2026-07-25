import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ExternalLink, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  usePortfolio,
  usePortfolioNews,
  usePortfolioQuotes,
  useRefreshPortfolio,
  useRemoveItem,
} from '@/hooks/usePortfolioQuery';
import { useMarketStream } from '@/hooks/useMarketStream';
import { AssetPicker } from '@modules/portfolio/components/AssetPicker';
import { QuotesTable } from '@modules/portfolio/components/QuotesTable';
import type { PortfolioItem } from '@/types/portfolio';

export function PortfolioDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id = '' } = useParams<{ id: string }>();

  // Live SSE: refetch quotes/news whenever a crawl publishes fresh data.
  useMarketStream({ notify: true });

  const { data: portfolio, isLoading } = usePortfolio(id);
  const { data: quotes = [] } = usePortfolioQuotes(id);
  const { data: news = [] } = usePortfolioNews(id);
  const refresh = useRefreshPortfolio(id);
  const removeItem = useRemoveItem(id);

  const handleRemove = (item: PortfolioItem) =>
    removeItem.mutate({ asset_type: item.asset_type, code: item.code });

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/portfolios')}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            {isLoading ? (
              <Skeleton className="h-7 w-40" />
            ) : (
              <h1 className="text-2xl font-bold tracking-tight">{portfolio?.name}</h1>
            )}
            {portfolio?.description && (
              <p className="text-sm text-muted-foreground">{portfolio.description}</p>
            )}
          </div>
        </div>
        <Button
          variant="outline"
          onClick={() => refresh.mutate('quotes')}
          disabled={refresh.isPending}
        >
          <RefreshCw className={`mr-1 h-4 w-4 ${refresh.isPending ? 'animate-spin' : ''}`} />
          {t('portfolio.refresh')}
        </Button>
      </div>

      <div className="mb-6 max-w-xl">
        <AssetPicker portfolioId={id} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">{t('portfolio.quotes')}</CardTitle>
          </CardHeader>
          <CardContent>
            <QuotesTable items={portfolio?.items ?? []} quotes={quotes} onRemove={handleRemove} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t('portfolio.news')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {news.length === 0 && (
              <p className="text-sm text-muted-foreground">{t('common.no_data')}</p>
            )}
            {news.slice(0, 15).map((n, i) => (
              <a
                key={`${n.symbol}-${n.news_id ?? i}`}
                href={n.url ?? '#'}
                target="_blank"
                rel="noreferrer"
                className="block rounded-md border border-border p-2 text-sm transition-colors hover:bg-accent"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium">{n.symbol}</span>
                  {n.url && <ExternalLink className="h-3 w-3 shrink-0 text-muted-foreground" />}
                </div>
                <p className="line-clamp-2 text-muted-foreground">{n.title}</p>
                {n.published_at && (
                  <p className="mt-1 text-xs text-muted-foreground">{n.published_at}</p>
                )}
              </a>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
