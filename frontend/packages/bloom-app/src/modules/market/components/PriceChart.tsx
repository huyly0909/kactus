import { type FC, useMemo } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { num } from '@/lib/format';
import type { OHLCV } from '@/types/market';

interface PriceChartProps {
  candles: OHLCV[];
  height?: number;
}

/** Close-price area chart over the OHLCV series (oldest → newest). */
export const PriceChart: FC<PriceChartProps> = ({ candles, height = 280 }) => {
  const data = useMemo(
    () =>
      candles.map((c) => ({
        time: c.time.slice(0, 10),
        close: num(c.close),
      })),
    [candles],
  );

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
        <defs>
          <linearGradient id="closeFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.35} />
            <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
          tickLine={false}
          axisLine={false}
          minTickGap={24}
        />
        <YAxis
          tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
          tickLine={false}
          axisLine={false}
          width={56}
          domain={['auto', 'auto']}
        />
        <Tooltip
          contentStyle={{
            background: 'var(--popover)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            fontSize: 12,
            color: 'var(--popover-foreground)',
          }}
        />
        <Area
          type="monotone"
          dataKey="close"
          stroke="var(--chart-1)"
          strokeWidth={2}
          fill="url(#closeFill)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
};
