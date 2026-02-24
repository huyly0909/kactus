import { type FC } from 'react';
import { Table, TextInput, Group, Pagination, Card, Text, Loader, Center } from '@mantine/core';
import { Search } from 'lucide-react';
import { useState } from 'react';

interface Column<T> {
    key: string;
    title: string;
    render?: (record: T, index: number) => React.ReactNode;
}

interface DataTableProps<T extends Record<string, unknown>> {
    columns: Column<T>[];
    data: T[];
    loading?: boolean;
    searchable?: boolean;
    searchPlaceholder?: string;
    pageSize?: number;
    title?: string;
    emptyMessage?: string;
}

/**
 * DataTable — rich table with search, pagination, and custom column rendering.
 * Built on Mantine Table.
 */
export const DataTable: FC<DataTableProps<Record<string, unknown>>> = ({
    columns,
    data,
    loading = false,
    searchable = true,
    searchPlaceholder = 'Search...',
    pageSize = 10,
    title,
    emptyMessage = 'No data found',
}) => {
    const [search, setSearch] = useState('');
    const [page, setPage] = useState(1);

    // Filter data by search term
    const filteredData = search
        ? data.filter((row) =>
            Object.values(row).some((value) =>
                String(value).toLowerCase().includes(search.toLowerCase()),
            ),
        )
        : data;

    // Paginate
    const totalPages = Math.ceil(filteredData.length / pageSize);
    const paginatedData = filteredData.slice((page - 1) * pageSize, page * pageSize);

    if (loading) {
        return (
            <Center py="xl">
                <Loader size="lg" />
            </Center>
        );
    }

    return (
        <Card shadow="sm" padding="lg" radius="md" withBorder>
            {(title || searchable) && (
                <Group justify="space-between" mb="md">
                    {title && (
                        <Text fw={600} size="lg">
                            {title}
                        </Text>
                    )}
                    {searchable && (
                        <TextInput
                            placeholder={searchPlaceholder}
                            leftSection={<Search size={16} />}
                            value={search}
                            onChange={(e) => {
                                setSearch(e.currentTarget.value);
                                setPage(1);
                            }}
                            w={300}
                        />
                    )}
                </Group>
            )}

            <Table striped highlightOnHover>
                <Table.Thead>
                    <Table.Tr>
                        {columns.map((col) => (
                            <Table.Th key={col.key}>{col.title}</Table.Th>
                        ))}
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {paginatedData.length === 0 ? (
                        <Table.Tr>
                            <Table.Td colSpan={columns.length}>
                                <Text ta="center" c="dimmed" py="md">
                                    {emptyMessage}
                                </Text>
                            </Table.Td>
                        </Table.Tr>
                    ) : (
                        paginatedData.map((row, index) => (
                            <Table.Tr key={index}>
                                {columns.map((col) => (
                                    <Table.Td key={col.key}>
                                        {col.render
                                            ? col.render(row, index)
                                            : String(row[col.key] ?? '')}
                                    </Table.Td>
                                ))}
                            </Table.Tr>
                        ))
                    )}
                </Table.Tbody>
            </Table>

            {totalPages > 1 && (
                <Group justify="center" mt="md">
                    <Pagination value={page} onChange={setPage} total={totalPages} />
                </Group>
            )}
        </Card>
    );
};
