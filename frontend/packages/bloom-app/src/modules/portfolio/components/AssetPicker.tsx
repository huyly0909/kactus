import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Search } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useAddItem, useAssetSearch } from '@/hooks/usePortfolioQuery';
import type { AssetType } from '@/types/portfolio';

const ASSET_TYPES: AssetType[] = ['STOCK', 'GOLD'];

/** Combobox to search the crawlable catalog and add an instrument. */
export function AssetPicker({ portfolioId }: { portfolioId: string }) {
  const { t } = useTranslation();
  const [assetType, setAssetType] = useState<AssetType>('STOCK');
  const [query, setQuery] = useState('');
  const { data: results = [], isFetching } = useAssetSearch({ asset_type: assetType, q: query });
  const addItem = useAddItem(portfolioId);

  const handleAdd = (code: string) => {
    addItem.mutate({ asset_type: assetType, code });
    setQuery('');
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        {ASSET_TYPES.map((type) => (
          <button
            key={type}
            onClick={() => setAssetType(type)}
            className={cn(
              'rounded-md px-3 py-1 text-xs font-medium transition-colors',
              assetType === type
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80',
            )}
          >
            {t(`portfolio.asset_type.${type}`)}
          </button>
        ))}
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value.toUpperCase())}
          placeholder={t('portfolio.search_asset')}
          className="pl-9"
        />

        {query.length >= 1 && (
          <div className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-md border border-border bg-popover shadow-lg">
            {isFetching && (
              <div className="px-3 py-2 text-sm text-muted-foreground">{t('common.loading')}</div>
            )}
            {!isFetching && results.length === 0 && (
              <div className="px-3 py-2 text-sm text-muted-foreground">
                {t('common.no_results')}
              </div>
            )}
            {results.map((asset) => {
              // Codes with no working price feed (e.g. DOJI, PNJ) stay listed so
              // users can see they are known — but adding one would only ever
              // show an empty row, so the entry is inert.
              const unavailable = !asset.is_crawlable;
              return (
                <button
                  key={asset.id}
                  disabled={unavailable}
                  title={unavailable ? t('portfolio.unavailable_hint') : undefined}
                  onClick={() => handleAdd(asset.code)}
                  className={cn(
                    'flex w-full items-center justify-between px-3 py-2 text-left text-sm',
                    unavailable ? 'cursor-not-allowed opacity-50' : 'hover:bg-accent',
                  )}
                >
                  <span className="flex items-center gap-2">
                    <span className="font-semibold">{asset.code}</span>
                    <span className="truncate text-muted-foreground">{asset.name}</span>
                    {unavailable && (
                      <Badge variant="outline" className="shrink-0 text-[10px]">
                        {t('portfolio.unavailable')}
                      </Badge>
                    )}
                    {asset.tags
                      ?.filter((tag) => tag !== 'disabled')
                      .map((tag) => (
                        <Badge key={tag} variant="secondary" className="text-[10px]">
                          {tag}
                        </Badge>
                      ))}
                  </span>
                  {!unavailable && <Plus className="h-4 w-4 shrink-0 text-muted-foreground" />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
