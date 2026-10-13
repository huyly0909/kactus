import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
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

  it('sorts rows when a sortable header is clicked', () => {
    const sortCols: DataTableColumn<Row>[] = [
      { key: 'code', title: 'Code' },
      { key: 'name', title: 'Name', sortable: true },
    ];
    const data: Row[] = [
      { id: '1', code: 'C1', name: 'Zeta' },
      { id: '2', code: 'C2', name: 'Alpha' },
    ];
    render(<DataTable columns={sortCols} data={data} searchable={false} />);
    const table = screen.getByRole('table');
    const firstNameCell = () => within(table).getAllByRole('row')[1].querySelectorAll('td')[1];
    expect(firstNameCell()).toHaveTextContent('Zeta'); // original order

    fireEvent.click(screen.getByRole('button', { name: /Name/ })); // asc
    expect(firstNameCell()).toHaveTextContent('Alpha');
  });

  it('delegates sorting instead of reordering rows when onSortChange is given', () => {
    // Under server pagination the visible rows are one page of a larger set, so
    // a header click must re-query — sorting them in place would only shuffle
    // the page and quietly lie about the ordering.
    const onSortChange = vi.fn();
    const sortCols: DataTableColumn<Row>[] = [
      { key: 'code', title: 'Code' },
      { key: 'name', title: 'Name', sortable: true },
    ];
    const data: Row[] = [
      { id: '1', code: 'C1', name: 'Zeta' },
      { id: '2', code: 'C2', name: 'Alpha' },
    ];
    render(
      <DataTable
        columns={sortCols}
        data={data}
        searchable={false}
        sort={{ key: 'name', desc: true }}
        onSortChange={onSortChange}
      />,
    );
    const table = screen.getByRole('table');
    const firstNameCell = () => within(table).getAllByRole('row')[1].querySelectorAll('td')[1];

    // Rendered exactly as handed over, despite a descending sort on `name`.
    expect(firstNameCell()).toHaveTextContent('Zeta');

    fireEvent.click(screen.getByRole('button', { name: /Name/ }));
    expect(onSortChange).toHaveBeenCalledWith({ key: 'name', desc: false });
    expect(firstNameCell()).toHaveTextContent('Zeta'); // still untouched
  });

  it('hides a column marked defaultHidden and keeps the rest', () => {
    const cols: DataTableColumn<Row>[] = [
      { key: 'code', title: 'Code' },
      { key: 'name', title: 'Name', defaultHidden: true },
    ];
    render(
      <DataTable columns={cols} data={makeRows(1)} searchable={false} enableColumnVisibility />,
    );
    expect(screen.getByText('Code')).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: 'Name' })).not.toBeInTheDocument();
    expect(screen.queryByText('Alpha')).not.toBeInTheDocument();
  });

  it('renders a server pagination range and pages via the callback', () => {
    const onPageChange = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={makeRows(10)}
        searchable={false}
        pagination={{ mode: 'server', page: 1, pageSize: 10, total: 25, onPageChange }}
      />,
    );
    expect(screen.getByText('1-10 / 25')).toBeInTheDocument();
    const buttons = screen.getAllByRole('button');
    const next = buttons.find((b) => !(b as HTMLButtonElement).disabled)!;
    fireEvent.click(next);
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('renders filter chips and removes them via the callback', () => {
    const onRemove = vi.fn();
    render(
      <DataTable
        columns={columns}
        data={makeRows(2)}
        searchable={false}
        filterChips={[{ id: 'f1', label: 'Type: Gold', onRemove }]}
      />,
    );
    expect(screen.getByText('Type: Gold')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'remove' }));
    expect(onRemove).toHaveBeenCalled();
  });

  it('renders rows as cards below the desktop breakpoint', () => {
    // setup.ts stubs matchMedia → matches:false → mobile tier → cards.
    render(
      <DataTable
        columns={columns}
        data={makeRows(2)}
        searchable={false}
        renderCard={(r) => <div data-testid="card">{r.name}</div>}
      />,
    );
    expect(screen.getAllByTestId('card')).toHaveLength(2);
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});
