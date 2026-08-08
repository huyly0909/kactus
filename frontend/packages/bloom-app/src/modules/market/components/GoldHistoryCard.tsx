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

/** Source groups in display order; anything else follows, alphabetically. */
const SOURCE_ORDER = ['sjc', 'mihong', 'yahoo'];

/** Select values must be unique, and `999` appears under more than one source.
 *  Same shape the backend uses for a series id (`gold_schedule_entity_id`). */
const seriesValue = (c: GoldHistoryCode) => `${c.source ?? ''}:${c.code}`;

/** Split on the FIRST colon only — PNJ codes contain their own
 *  (`pnj:PNJ:Hà Nội:Vàng 916`), so `split(':')` would mangle them. */
function parseSeriesValue(v: string): { source: string; code: string } {
  const i = v.indexOf(':');
  return i < 0 ? { source: '', code: v } : { source: v.slice(0, i), code: v.slice(i + 1) };
}

/**
 * Historical price chart over the imported gold series.
 *
 * One series at a time: the catalogue mixes VND/lượng and USD/oz, and a single
 * selection is what guarantees the axis never mixes units. Series are grouped
 * by **source**, because `code` alone is ambiguous — SJC and Mihong both quote
 * `999` as different products. Groups come from the data, so a source with no
 * stored history simply does not appear. PNJ contributes ~160 series, so that
 * group is sorted by depth (point count) rather than by code; the Radix Select
 * keeps them keyboard-typeahead searchable.
 */
export const GoldHistoryCard: FC = () => {
  const { t } = useTranslation();
  const { data: codes, isLoading: codesLoading } = useGoldHistoryCodes();
  const [selected, setSelected] = useState<string>('');
  // A single { from, to } range drives the view — a preset chip and a custom
  // calendar pick emit the same shape. Default: trailing 1 year.
  const [range, setRange] = useState<DateRange>(defaultRange);

  // One group per source, each sorted by code — except PNJ, whose ~160 series
  // are far more useful ordered by depth.
  const groups = useMemo(() => {
    const bySource = new Map<string, GoldHistoryCode[]>();
    for (const c of codes ?? []) {
      const s = c.source ?? '';
      if (!bySource.has(s)) bySource.set(s, []);
      bySource.get(s)!.push(c);
    }
    return [...bySource.entries()]
      .sort(([a], [b]) => {
        const ia = SOURCE_ORDER.indexOf(a);
        const ib = SOURCE_ORDER.indexOf(b);
        if (ia !== ib)
          return (ia < 0 ? SOURCE_ORDER.length : ia) - (ib < 0 ? SOURCE_ORDER.length : ib);
        return a.localeCompare(b);
      })
      .map(([source, items]) => ({
        source,
        items: [...items].sort((a, b) =>
          source === 'pnj' ? Number(b.points) - Number(a.points) : a.code.localeCompare(b.code),
        ),
      }));
  }, [codes]);

  // Default to the first series of the first group once the list loads.
  const first = groups[0]?.items[0];
  const value = selected || (first ? seriesValue(first) : '');
  const { source, code } = parseSeriesValue(value);
  const unit =
    (codes ?? []).find((c) => c.code === code && (c.source ?? '') === source)?.unit ?? '';

  const historyParams: GoldHistoryParams = {
    source: source || undefined,
    start: range.from || undefined,
    end: range.to || undefined,
    limit: rangeLimit(range),
  };

  const { data: points, isLoading: pointsLoading } = useGoldHistory(code, historyParams);

  if (!codesLoading && (codes ?? []).length === 0) return null;

  const label = (c: GoldHistoryCode) =>
    c.source === 'pnj' ? `${c.gold_type ?? c.code} — ${c.location ?? ''}` : c.code;

  return (
    <Card className="mb-6">
      <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <CardTitle className="text-base">{t('market.gold.history.title')}</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={value} onValueChange={setSelected}>
            <SelectTrigger className="w-64">
              <SelectValue placeholder={t('market.gold.history.series')} />
            </SelectTrigger>
            <SelectContent>
              {groups.map((g) => (
                <SelectGroup key={g.source}>
                  <SelectLabel>
                    {t(`market.gold.history.group_source.${g.source}`, {
                      defaultValue: g.source,
                    })}
                  </SelectLabel>
                  {g.items.map((c) => (
                    <SelectItem key={seriesValue(c)} value={seriesValue(c)}>
                      {label(c)}
                      {c.unit === UNIT_USD_PER_OZ ? ' (USD/oz)' : ''}
                    </SelectItem>
                  ))}
                </SelectGroup>
              ))}
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
