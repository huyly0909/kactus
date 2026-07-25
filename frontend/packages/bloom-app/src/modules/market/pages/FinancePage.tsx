import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FileSpreadsheet, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useFinanceReports } from '@/hooks/useMarketQuery';
import { fmtCompact, fmtDateTime, num } from '@/lib/format';
import type { FinanceReport, ReportPeriod, ReportType } from '@/types/market';

const REPORT_TYPES: ReportType[] = ['income_statement', 'balance_sheet', 'cash_flow', 'ratio'];
const PERIODS: ReportPeriod[] = ['quarter', 'year'];

/** Keys that identify the period rather than a financial figure. */
const META_KEYS = new Set(['year', 'quarter', 'ticker', 'symbol', 'Year', 'Quarter', 'CP']);

function periodLabel(r: FinanceReport): string {
  const q = num(r.quarter);
  return r.period === 'quarter' && q ? `${r.year} Q${q}` : String(r.year);
}

function cellValue(v: unknown): string {
  if (v == null || v === '') return '—';
  if (typeof v === 'number') return fmtCompact(v);
  if (typeof v === 'string' && v.trim() !== '' && !Number.isNaN(Number(v))) return fmtCompact(v);
  return String(v);
}

/** Financial statements — a symbol's reports pivoted period-by-period. */
export function FinancePage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();

  const symbol = (params.get('symbol') ?? '').toUpperCase();
  const [input, setInput] = useState(symbol);
  const [reportType, setReportType] = useState<ReportType>('income_statement');
  const [period, setPeriod] = useState<ReportPeriod>('quarter');

  const { data: reports, isLoading } = useFinanceReports(symbol, {
    report_type: reportType,
    period,
    limit: 8,
  });

  // Union of every metric key across the returned periods, in first-seen order.
  const metrics = useMemo(() => {
    const keys: string[] = [];
    for (const r of reports ?? []) {
      for (const k of Object.keys(r.data ?? {})) {
        if (!META_KEYS.has(k) && !keys.includes(k)) keys.push(k);
      }
    }
    return keys;
  }, [reports]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const next = input.trim().toUpperCase();
    setParams(next ? { symbol: next } : {});
  };

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/10 text-primary">
          <FileSpreadsheet className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('market.finance.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('market.finance.subtitle')}</p>
        </div>
      </div>

      <div className="mb-6 flex flex-wrap items-end gap-3">
        <form onSubmit={submit} className="flex items-end gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t('market.finance.symbol_placeholder')}
              className="w-44 pl-8 uppercase"
            />
          </div>
          <Button type="submit">{t('common.search')}</Button>
        </form>

        <Select value={reportType} onValueChange={(v) => setReportType(v as ReportType)}>
          <SelectTrigger className="w-52">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {REPORT_TYPES.map((rt) => (
              <SelectItem key={rt} value={rt}>
                {t(`market.finance.report_type.${rt}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={period} onValueChange={(v) => setPeriod(v as ReportPeriod)}>
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PERIODS.map((p) => (
              <SelectItem key={p} value={p}>
                {t(`market.finance.period.${p}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {!symbol && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16 text-center">
          <FileSpreadsheet className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t('market.finance.pick_symbol')}</p>
        </div>
      )}

      {symbol && isLoading && <Skeleton className="h-64 w-full" />}

      {symbol && !isLoading && metrics.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16 text-center">
          <p className="text-sm text-muted-foreground">{t('market.finance.empty')}</p>
        </div>
      )}

      {symbol && !isLoading && metrics.length > 0 && (
        <>
          <div className="rounded-md border border-border">
            <Table>
              <TableHeader>
                <TableRow className="border-t-0">
                  <TableHead className="min-w-64">{t('market.finance.metric')}</TableHead>
                  {(reports ?? []).map((r) => (
                    <TableHead key={periodLabel(r)} className="text-right whitespace-nowrap">
                      {periodLabel(r)}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {metrics.map((key) => (
                  <TableRow key={key}>
                    <TableCell className="font-medium">{key}</TableCell>
                    {(reports ?? []).map((r) => (
                      <TableCell
                        key={`${key}-${periodLabel(r)}`}
                        className="text-right tabular-nums whitespace-nowrap"
                      >
                        {cellValue(r.data?.[key])}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {t('market.updated_at')}: {fmtDateTime(reports?.[0]?.synced_at)}
          </p>
        </>
      )}
    </div>
  );
}
