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

  const fmtValue = (v: number) => fmtGold(v, unit);

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
        <Tooltip
          contentStyle={{
            background: 'var(--popover)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            fontSize: 12,
            color: 'var(--popover-foreground)',
          }}
          formatter={(value, name) => [
            typeof value === 'number' ? fmtValue(value) : String(value ?? '—'),
            String(name ?? ''),
          ]}
        />
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
