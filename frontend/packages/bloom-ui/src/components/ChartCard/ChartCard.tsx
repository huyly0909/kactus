import { type FC, type ReactNode } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';

type ChartType = 'line' | 'bar' | 'area';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  data: Record<string, unknown>[];
  type?: ChartType;
  dataKey: string;
  xAxisKey?: string;
  color?: string;
  height?: number;
  extra?: ReactNode;
}

/**
 * ChartCard — card with a title and an embedded Recharts chart.
 * shadcn/Tailwind port (previously Mantine `Card`). Supports line/bar/area.
 * `color` defaults to the design-system `--chart-1` token.
 */
export const ChartCard: FC<ChartCardProps> = ({
  title,
  subtitle,
  data,
  type = 'line',
  dataKey,
  xAxisKey = 'name',
  color = 'var(--chart-1)',
  height = 300,
  extra,
}) => {
  const renderChart = () => {
    const commonProps = { data, margin: { top: 5, right: 20, left: 0, bottom: 5 } };

    switch (type) {
      case 'bar':
        return (
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey={xAxisKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} />
          </BarChart>
        );

      case 'area':
        return (
          <AreaChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey={xAxisKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              fill={color}
              fillOpacity={0.15}
            />
          </AreaChart>
        );

      case 'line':
      default:
        return (
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey={xAxisKey} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} />
          </LineChart>
        );
    }
  };

  return (
    <div className="rounded-lg border border-border bg-card p-6 text-card-foreground shadow-sm">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <p className="text-lg font-semibold leading-none tracking-tight">{title}</p>
          {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
        </div>
        {extra}
      </div>

      <ResponsiveContainer width="100%" height={height}>
        {renderChart()}
      </ResponsiveContainer>
    </div>
  );
};
