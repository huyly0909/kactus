import { type FC } from 'react';
import { SimpleGrid, Card, Group, Text, ThemeIcon, Title, Stack } from '@mantine/core';
import { DollarSign, TrendingUp, Users, Activity } from 'lucide-react';
import { ChartCard } from '@kactus-bloom/ui';
import { formatCurrency, formatNumber } from '@kactus-bloom/ui/utils';

// Sample dashboard data — replace with real API calls using TanStack Query
const stats = [
    { title: 'Total Revenue', value: 2456789, icon: DollarSign, color: 'green', format: 'currency' },
    { title: 'Growth Rate', value: 12.5, icon: TrendingUp, color: 'blue', format: 'percent' },
    { title: 'Active Users', value: 8432, icon: Users, color: 'violet', format: 'number' },
    { title: 'Transactions', value: 15678, icon: Activity, color: 'orange', format: 'number' },
] as const;

const revenueData = [
    { name: 'Jan', revenue: 4000 },
    { name: 'Feb', revenue: 3200 },
    { name: 'Mar', revenue: 5800 },
    { name: 'Apr', revenue: 4900 },
    { name: 'May', revenue: 6200 },
    { name: 'Jun', revenue: 7100 },
];

const transactionData = [
    { name: 'Mon', count: 120 },
    { name: 'Tue', count: 180 },
    { name: 'Wed', count: 150 },
    { name: 'Thu', count: 210 },
    { name: 'Fri', count: 190 },
    { name: 'Sat', count: 90 },
    { name: 'Sun', count: 60 },
];

const formatValue = (value: number, format: string) => {
    switch (format) {
        case 'currency':
            return formatCurrency(value);
        case 'percent':
            return `${value}%`;
        case 'number':
            return formatNumber(value);
        default:
            return String(value);
    }
};

export const DashboardPage: FC = () => {
    return (
        <Stack gap="lg">
            <Title order={2}>Dashboard</Title>

            {/* KPI Cards */}
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
                {stats.map((stat) => (
                    <Card key={stat.title} shadow="sm" padding="lg" radius="md" withBorder>
                        <Group justify="space-between">
                            <div>
                                <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
                                    {stat.title}
                                </Text>
                                <Text size="xl" fw={700} mt={4}>
                                    {formatValue(stat.value, stat.format)}
                                </Text>
                            </div>
                            <ThemeIcon size="lg" radius="md" variant="light" color={stat.color}>
                                <stat.icon size={20} />
                            </ThemeIcon>
                        </Group>
                    </Card>
                ))}
            </SimpleGrid>

            {/* Charts */}
            <SimpleGrid cols={{ base: 1, lg: 2 }}>
                <ChartCard
                    title="Monthly Revenue"
                    subtitle="Last 6 months"
                    data={revenueData}
                    type="area"
                    dataKey="revenue"
                    color="#6366f1"
                />
                <ChartCard
                    title="Daily Transactions"
                    subtitle="This week"
                    data={transactionData}
                    type="bar"
                    dataKey="count"
                    color="#22c55e"
                />
            </SimpleGrid>
        </Stack>
    );
};
