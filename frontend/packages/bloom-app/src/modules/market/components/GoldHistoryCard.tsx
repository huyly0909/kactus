import { type FC, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import { DateRangeControl, datePresets, type DateRange } from '@/components/ui/date-range-picker';
import { useGoldHistory, useGoldHistoryCodes } from '@/hooks/useMarketQuery';
import type { GoldHistoryParams } from '@/services/marketService';
import { UNIT_USD_PER_OZ, type GoldHistoryCode } from '@/types/market';
import { GoldHistoryChart } from './GoldHistoryChart';

// Quick selections for the gold chart: this week / month / quarter, then
// trailing 1/3/5 years, then all-time. The widget hardcodes no presets — each
// chart passes the ones it needs.
const GOLD_PRESETS = datePresets('week', 'month', 'quarter', '1y', '3y', '5y', 'all');
const defaultRange = (): DateRange => datePresets('1y')[0]?.range() ?? { from: '', to: '' };

const DAY_MS = 86_400_000;

/**
 * Points to fetch for a range: ~one row per calendar day plus headroom. An
 * unbounded ("all") range clears the backend's default cap — XAU alone is ~6.5k
 * points.
 */
function rangeLimit(r: DateRange): number {
  if (!r.from) return 10_000;
  const from = new Date(r.from).getTime();
  const to = (r.to ? new Date(r.to) : new Date()).getTime();
  const days = Math.max(1, Math.round((to - from) / DAY_MS));
  return Math.min(10_000, days + 60);
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
  // A single { from, to } range drives the view — a preset chip and a custom
  // calendar pick emit the same shape. Default: trailing 1 year.
  const [range, setRange] = useState<DateRange>(defaultRange);

  const historyParams: GoldHistoryParams = {
    start: range.from || undefined,
    end: range.to || undefined,
    limit: rangeLimit(range),
  };

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

  const { data: points, isLoading: pointsLoading } = useGoldHistory(code, historyParams);

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
          <DateRangeControl
            value={range}
            onChange={setRange}
            presets={GOLD_PRESETS}
            placeholder={t('common.range_custom')}
          />
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
