import { type FC, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { fmtGold, num } from '@/lib/format';
import type { GoldHistoryPoint } from '@/types/market';

interface GoldHistoryChartProps {
  points: GoldHistoryPoint[];
  /** Unit of the (single) series — the axis/tooltip formatter depends on it. */
  unit: string;
  height?: number;
}

interface TooltipPayloadItem {
  name?: string | number;
  value?: number | string;
  color?: string;
  dataKey?: string | number;
}

interface GoldHistoryTooltipProps {
  active?: boolean;
  label?: string | number;
  payload?: TooltipPayloadItem[];
  /** Unit of the series — decides VND/lượng vs USD/oz formatting. */
  unit: string;
}

/**
 * Custom tooltip.
 *
 * Recharts renders its default container even when the active payload is empty
 * — that is the stray empty box that appears in the right-margin dead zone just
 * past the final data point (the last point sits flush against the edge, so the
 * cursor lands there while trying to read it). Returning `null` on an empty
 * payload suppresses the box; every real point still renders its values.
 */
const GoldHistoryTooltip: FC<GoldHistoryTooltipProps> = ({ active, label, payload, unit }) => {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <div className="mb-1 font-medium">{String(label ?? '')}</div>
      {payload.map((item) => (
        <div
          key={String(item.dataKey ?? item.name)}
          className="flex items-center justify-between gap-4"
        >
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: item.color }}
            />
            {String(item.name ?? '')}
          </span>
          <span className="tabular-nums">
            {typeof item.value === 'number' ? fmtGold(item.value, unit) : String(item.value ?? '—')}
          </span>
        </div>
      ))}
    </div>
  );
};

/**
 * One gold series over time. Domestic series carry buy/sell lines; world gold
 * (XAU) carries a close line. Only ever renders ONE series, so VND/lượng and
 * USD/oz can never share an axis.
 */
export const GoldHistoryChart: FC<GoldHistoryChartProps> = ({ points, unit, height = 300 }) => {
  const { t } = useTranslation();

  const { data, hasBuySell } = useMemo(() => {
    const rows = points.map((p) => ({
      date: p.date,
      buy: num(p.buy_price),
      sell: num(p.sell_price),
      close: num(p.close),
    }));
    return { data: rows, hasBuySell: rows.some((r) => r.buy != null || r.sell != null) };
  }, [points]);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <defs>
          <linearGradient id="goldSellFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.3} />
            <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
          tickLine={false}
          axisLine={false}
          minTickGap={32}
        />
        <YAxis
          tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
          tickLine={false}
          axisLine={false}
          width={72}
          domain={['auto', 'auto']}
          tickFormatter={(v: number) =>
            v.toLocaleString(undefined, { notation: 'compact', maximumFractionDigits: 1 })
          }
        />
        <Tooltip content={<GoldHistoryTooltip unit={unit} />} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {hasBuySell ? (
          <>
            <Area
              type="monotone"
              dataKey="sell"
              name={t('market.gold.sell')}
              stroke="var(--chart-1)"
              strokeWidth={2}
              fill="url(#goldSellFill)"
              dot={false}
            />
            <Area
              type="monotone"
              dataKey="buy"
              name={t('market.gold.buy')}
              stroke="var(--chart-2)"
              strokeWidth={2}
              fill="none"
              dot={false}
            />
          </>
        ) : (
          <Area
            type="monotone"
            dataKey="close"
            name={t('market.gold.history.close')}
            stroke="var(--chart-1)"
            strokeWidth={2}
            fill="url(#goldSellFill)"
            dot={false}
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
};
