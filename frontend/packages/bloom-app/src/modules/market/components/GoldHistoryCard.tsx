import { type FC, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useGoldHistory, useGoldHistoryCodes } from '@/hooks/useMarketQuery';
import { UNIT_USD_PER_OZ, type GoldHistoryCode } from '@/types/market';
import { GoldHistoryChart } from './GoldHistoryChart';

type RangeKey = '1y' | '5y' | 'max';

/** "Max" must clear the backend's default cap — XAU alone is ~6.5k points. */
const RANGE_LIMIT: Record<RangeKey, number> = { '1y': 400, '5y': 2000, max: 10_000 };

function rangeStart(range: RangeKey): string | undefined {
  if (range === 'max') return undefined;
  const d = new Date();
  d.setFullYear(d.getFullYear() - (range === '1y' ? 1 : 5));
  return d.toISOString().slice(0, 10);
}

/**
 * Historical price chart over the imported gold series.
 *
 * One series at a time: the catalogue mixes VND/lượng and USD/oz, and a single
 * selection is what guarantees the axis never mixes units. PNJ contributes
 * ~160 series, so they live in their own group sorted by depth (point count);
 * the Radix Select keeps them keyboard-typeahead searchable.
 */
export const GoldHistoryCard: FC = () => {
  const { t } = useTranslation();
  const { data: codes, isLoading: codesLoading } = useGoldHistoryCodes();
  const [selected, setSelected] = useState<string>('');
  const [range, setRange] = useState<RangeKey>('1y');

  const { primary, pnj } = useMemo(() => {
    const all = codes ?? [];
    const isPnj = (c: GoldHistoryCode) => c.code.startsWith('PNJ:');
    return {
      primary: all.filter((c) => !isPnj(c)),
      pnj: all.filter(isPnj).sort((a, b) => Number(b.points) - Number(a.points)),
    };
  }, [codes]);

  // Default to the first non-PNJ series (SJC in practice) once the list loads.
  const code = selected || primary[0]?.code || '';
  const unit = (codes ?? []).find((c) => c.code === code)?.unit ?? '';

  const { data: points, isLoading: pointsLoading } = useGoldHistory(code, {
    start: rangeStart(range),
    limit: RANGE_LIMIT[range],
  });

  if (!codesLoading && (codes ?? []).length === 0) return null;

  const label = (c: GoldHistoryCode) =>
    c.code.startsWith('PNJ:') ? `${c.gold_type ?? c.code} — ${c.location ?? ''}` : c.code;

  return (
    <Card className="mb-6">
      <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <CardTitle className="text-base">{t('market.gold.history.title')}</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={code} onValueChange={setSelected}>
            <SelectTrigger className="w-64">
              <SelectValue placeholder={t('market.gold.history.series')} />
            </SelectTrigger>
            <SelectContent>
              {primary.length > 0 && (
                <SelectGroup>
                  <SelectLabel>{t('market.gold.history.group_main')}</SelectLabel>
                  {primary.map((c) => (
                    <SelectItem key={c.code} value={c.code}>
                      {label(c)}
                      {c.unit === UNIT_USD_PER_OZ ? ' (USD/oz)' : ''}
                    </SelectItem>
                  ))}
                </SelectGroup>
              )}
              {pnj.length > 0 && (
                <SelectGroup>
                  <SelectLabel>PNJ</SelectLabel>
                  {pnj.map((c) => (
                    <SelectItem key={c.code} value={c.code}>
                      {label(c)}
                    </SelectItem>
                  ))}
                </SelectGroup>
              )}
            </SelectContent>
          </Select>
          <div className="flex gap-1">
            {(['1y', '5y', 'max'] as const).map((r) => (
              <Button
                key={r}
                size="sm"
                variant={range === r ? 'default' : 'outline'}
                onClick={() => setRange(r)}
              >
                {t(`market.gold.history.range_${r}`)}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {pointsLoading || codesLoading ? (
          <Skeleton className="h-[300px] w-full" />
        ) : (points ?? []).length === 0 ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            {t('market.gold.history.empty')}
          </p>
        ) : (
          <>
            <GoldHistoryChart points={points ?? []} unit={unit} />
            <p className="mt-2 text-right text-xs text-muted-foreground">
              {unit === UNIT_USD_PER_OZ
                ? t('market.gold.unit_usd_oz')
                : t('market.gold.unit_vnd_luong')}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
};
