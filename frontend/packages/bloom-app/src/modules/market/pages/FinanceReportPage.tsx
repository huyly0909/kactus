import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { FileSpreadsheet, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ReportView, type ReportColumn, type ReportRow } from '@/components/report-view';
import { useFinanceReports } from '@/hooks/useMarketQuery';
import { num } from '@/lib/format';
import type { FinanceReport, ReportPeriod, ReportType } from '@/types/market';

const REPORT_TYPES: ReportType[] = ['income_statement', 'balance_sheet', 'cash_flow', 'ratio'];
const PERIODS: ReportPeriod[] = ['quarter', 'year'];
const META_KEYS = new Set(['year', 'quarter', 'ticker', 'symbol', 'Year', 'Quarter', 'CP']);

function periodLabel(r: FinanceReport): string {
  const q = num(r.quarter);
  return r.period === 'quarter' && q ? `${r.year} Q${q}` : String(r.year);
}

/**
 * POC — the finance pivot rebuilt on the ReportView primitive (metric rows ×
 * period columns), at a throwaway route so the existing FinancePage stays
 * untouched. A collapsible section header groups the metric rows; every value
 * column formats through the report format seam. Flip `market/finance` to this
 * once it earns its keep.
 */
export function FinanceReportPage() {
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

  const metrics = useMemo(() => {
    const keys: string[] = [];
    for (const r of reports ?? []) {
      for (const k of Object.keys(r.data ?? {})) {
        if (!META_KEYS.has(k) && !keys.includes(k)) keys.push(k);
      }
    }
    return keys;
  }, [reports]);

  const columns = useMemo<ReportColumn[]>(
    () =>
      (reports ?? []).map((r, i) => ({
        id: `p${i}`,
        header: periodLabel(r),
        align: 'right',
        kind: 'money',
      })),
    [reports],
  );

  const rows = useMemo<ReportRow[]>(() => {
    if (metrics.length === 0) return [];
    const sectionId = 'section';
    const header: ReportRow = {
      id: sectionId,
      kind: 'section',
      label: t(`market.finance.report_type.${reportType}`),
      collapsible: true,
    };
    const dataRows: ReportRow[] = metrics.map((metric) => ({
      id: `m-${metric}`,
      kind: 'data',
      label: metric,
      depth: 1,
      groupId: sectionId,
      values: Object.fromEntries(
        (reports ?? []).map((r, i) => [`p${i}`, (r.data ?? {})[metric] as number | string | null]),
      ),
    }));
    return [header, ...dataRows];
  }, [metrics, reports, reportType, t]);

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

      {symbol && (
        <ReportView
          columns={columns}
          rows={rows}
          rowHeaderLabel={t('market.finance.metric')}
          loading={isLoading}
          emptyMessage={t('market.finance.empty')}
        />
      )}
    </div>
  );
}
