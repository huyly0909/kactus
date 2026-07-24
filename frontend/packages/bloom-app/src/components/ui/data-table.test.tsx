import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { DataTable, type DataTableColumn } from './data-table';

interface Row {
  id: string;
  code: string;
  name: string;
}

const columns: DataTableColumn<Row>[] = [
  { key: 'code', title: 'Code' },
  { key: 'name', title: 'Name' },
];

const makeRows = (n: number): Row[] =>
  Array.from({ length: n }, (_, i) => ({
    id: String(i),
    code: `C${i}`,
    name: i === 0 ? 'Alpha' : `Row ${i}`,
  }));

describe('DataTable', () => {
  it('renders rows and a custom empty message', () => {
    render(
      <DataTable columns={columns} data={[]} emptyMessage="Nothing here" searchable={false} />,
    );
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
  });

  it('renders provided data', () => {
    render(<DataTable columns={columns} data={makeRows(3)} searchable={false} />);
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('C1')).toBeInTheDocument();
  });

  it('filters rows by the search box', () => {
    render(<DataTable columns={columns} data={makeRows(5)} searchPlaceholder="Search" />);
    const input = screen.getByPlaceholderText('Search');
    fireEvent.change(input, { target: { value: 'Alpha' } });
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.queryByText('Row 2')).not.toBeInTheDocument();
  });

  it('paginates when data exceeds pageSize', () => {
    render(<DataTable columns={columns} data={makeRows(25)} pageSize={10} searchable={false} />);
    // page indicator shows 1 / 3
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    // only 10 body rows on the first page
    const table = screen.getByRole('table');
    const bodyRows = within(table).getAllByRole('row').slice(1); // drop header row
    expect(bodyRows).toHaveLength(10);
  });

  it('renders a cell via a custom render function', () => {
    const withRender: DataTableColumn<Row>[] = [
      { key: 'code', title: 'Code', render: (r) => <span data-testid="rendered">{r.code}!</span> },
    ];
    render(<DataTable columns={withRender} data={makeRows(1)} searchable={false} />);
    expect(screen.getByTestId('rendered')).toHaveTextContent('C0!');
  });
});
