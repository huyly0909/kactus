import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ExternalLink } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useOHLCV, useStock, useStockNews } from '@/hooks/useMarketQuery';
import { fmt, fmtChange, fmtCompact, fmtDateTime, toneOf } from '@/lib/format';
import { cn } from '@/lib/utils';
import { PriceChart } from '@modules/market/components/PriceChart';
import type { OHLCVInterval } from '@/types/market';

const INTERVALS: OHLCVInterval[] = ['1D', '1W', '1M'];

interface StatProps {
  label: string;
  value: string;
  className?: string;
}

function Stat({ label, value, className }: StatProps) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn('text-lg font-semibold tabular-nums', className)}>{value}</p>
    </div>
  );
}

/** One symbol — company profile, latest quote, price history and news. */
export function StockDetailPage() {
  const { t } = useTranslation();
  const { symbol = '' } = useParams<{ symbol: string }>();
  const [interval, setInterval] = useState<OHLCVInterval>('1D');

  const { data: detail, isLoading, isError } = useStock(symbol);
  const { data: candles, isLoading: candlesLoading } = useOHLCV(symbol, { interval, limit: 180 });
  const { data: news } = useStockNews(symbol);

  if (isLoading) {
    return (
      <div className="space-y-4 p-6 md:p-8">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !detail) {
    return (
      <div className="p-6 md:p-8">
        <p className="text-sm text-muted-foreground">{t('market.stock.not_found')}</p>
        <Button variant="outline" className="mt-4" asChild>
          <Link to="/market/stocks">
            <ArrowLeft className="mr-1 h-4 w-4" />
            {t('common.back')}
          </Link>
        </Button>
      </div>
    );
  }

  const quote = detail.quote;
  const company = detail.company;

  return (
    <div className="p-6 md:p-8">
      <Button variant="ghost" size="sm" className="mb-4 -ml-2" asChild>
        <Link to="/market/stocks">
          <ArrowLeft className="mr-1 h-4 w-4" />
          {t('market.stock.title')}
        </Link>
      </Button>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold tracking-tight">{detail.symbol}</h1>
        {company?.exchange && <Badge variant="secondary">{company.exchange}</Badge>}
        {company?.industry && <Badge variant="outline">{company.industry}</Badge>}
        <span className="text-sm text-muted-foreground">
          {company?.company_name ?? detail.organ_name ?? ''}
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">{t('market.stock.price_history')}</CardTitle>
            <Select value={interval} onValueChange={(v) => setInterval(v as OHLCVInterval)}>
              <SelectTrigger className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INTERVALS.map((iv) => (
                  <SelectItem key={iv} value={iv}>
                    {t(`market.interval.${iv}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent>
            {candlesLoading && <Skeleton className="h-64 w-full" />}
            {!candlesLoading && (candles?.length ?? 0) === 0 && (
              <p className="py-20 text-center text-sm text-muted-foreground">
                {t('market.stock.no_history')}
              </p>
            )}
            {!candlesLoading && (candles?.length ?? 0) > 0 && (
              <PriceChart candles={candles ?? []} />
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('market.stock.quote')}</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <Stat label={t('market.stock.price')} value={fmt(quote?.match_price)} />
              <Stat
                label={t('market.stock.change')}
                value={fmtChange(quote?.change, quote?.change_pct)}
                className={toneOf(quote?.change)}
              />
              <Stat label={t('market.stock.ref')} value={fmt(quote?.ref_price)} />
              <Stat
                label={t('market.stock.volume')}
                value={fmtCompact(quote?.accumulated_volume)}
              />
              <Stat label={t('market.stock.ceiling')} value={fmt(quote?.ceiling)} />
              <Stat label={t('market.stock.floor')} value={fmt(quote?.floor)} />
              <div className="col-span-2 text-xs text-muted-foreground">
                {t('market.updated_at')}: {fmtDateTime(quote?.crawled_at)}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t('market.stock.profile')}</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <Stat label={t('market.stock.market_cap')} value={fmtCompact(company?.market_cap)} />
              <Stat
                label={t('market.stock.shares')}
                value={fmtCompact(company?.outstanding_shares)}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">{t('market.stock.news')}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {(news?.length ?? 0) === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              {t('market.stock.no_news')}
            </p>
          )}
          {news?.map((n) => (
            <a
              key={`${n.news_id}-${n.published_at}`}
              href={n.url ?? '#'}
              target="_blank"
              rel="noreferrer"
              className="flex items-center justify-between gap-4 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent"
            >
              <span className="truncate">{n.title ?? '—'}</span>
              <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                {n.published_at ?? ''}
                <ExternalLink className="h-3.5 w-3.5" />
              </span>
            </a>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
