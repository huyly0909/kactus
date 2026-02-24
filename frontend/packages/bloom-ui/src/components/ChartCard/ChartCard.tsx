import { type FC, type ReactNode } from 'react';
import { Card, Group, Text } from '@mantine/core';
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
 * Supports line, bar, and area chart types.
 */
export const ChartCard: FC<ChartCardProps> = ({
    title,
    subtitle,
    data,
    type = 'line',
    dataKey,
    xAxisKey = 'name',
    color = '#6366f1',
    height = 300,
    extra,
}) => {
    const renderChart = () => {
        const commonProps = {
            data,
            margin: { top: 5, right: 20, left: 0, bottom: 5 },
        };

        switch (type) {
            case 'bar':
                return (
                    <BarChart {...commonProps}>
                        <CartesianGrid strokeDasharray="3 3" />
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
                        <CartesianGrid strokeDasharray="3 3" />
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
                        <CartesianGrid strokeDasharray="3 3" />
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
        <Card shadow="sm" padding="lg" radius="md" withBorder>
            <Group justify="space-between" mb="md">
                <div>
                    <Text fw={600} size="lg">{title}</Text>
                    {subtitle && <Text size="sm" c="dimmed">{subtitle}</Text>}
                </div>
                {extra}
            </Group>

            <ResponsiveContainer width="100%" height={height}>
                {renderChart()}
            </ResponsiveContainer>
        </Card>
    );
};
