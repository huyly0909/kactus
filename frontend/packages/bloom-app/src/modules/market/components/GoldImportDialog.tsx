import { useRef, useState, type DragEvent, type FC } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { FileUp, Loader2, Trash2, Upload } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import { useImportGoldHistory } from '@/hooks/useMarketQuery';
import type { GoldImportResult } from '@/types/market';

interface GoldImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Drag-and-drop import of historical gold CSVs (SJC / world XAU / PNJ
 * backfill files). The backend detects the format from the header row and
 * answers with per-file counts, rendered inline after the upload.
 */
export const GoldImportDialog: FC<GoldImportDialogProps> = ({ open, onOpenChange }) => {
  const { t } = useTranslation();
  const importMutation = useImportGoldHistory();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [results, setResults] = useState<GoldImportResult[]>([]);
  const [dragging, setDragging] = useState(false);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    const csvs = Array.from(incoming).filter((f) => f.name.toLowerCase().endsWith('.csv'));
    if (csvs.length < (incoming.length ?? 0)) {
      toast.error(t('market.gold.import.only_csv'));
    }
    // Re-adding a file with the same name replaces the staged one.
    setFiles((prev) => [...prev.filter((p) => !csvs.some((c) => c.name === p.name)), ...csvs]);
    setResults([]);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  };

  const handleOpenChange = (o: boolean) => {
    if (!o) {
      setFiles([]);
      setResults([]);
    }
    onOpenChange(o);
  };

  const onImport = async () => {
    try {
      const res = await importMutation.mutateAsync(files);
      setResults(res);
      setFiles([]);
      toast.success(t('market.gold.import.success'));
    } catch {
      toast.error(t('market.gold.import.failed'));
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('market.gold.import.title')}</DialogTitle>
        </DialogHeader>

        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed p-8 text-center transition-colors',
            dragging ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50',
          )}
        >
          <Upload className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t('market.gold.import.drop_hint')}</p>
          <p className="text-xs text-muted-foreground">{t('market.gold.import.browse')}</p>
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            multiple
            className="hidden"
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = '';
            }}
          />
        </div>

        {files.length > 0 && (
          <ul className="space-y-1">
            {files.map((f) => (
              <li
                key={f.name}
                className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
              >
                <span className="flex items-center gap-2 truncate">
                  <FileUp className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="truncate">{f.name}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {(f.size / 1024).toLocaleString(undefined, { maximumFractionDigits: 0 })} KB
                  </span>
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setFiles((prev) => prev.filter((p) => p.name !== f.name))}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}

        {results.length > 0 && (
          <ul className="space-y-1">
            {results.map((r, i) => (
              <li
                key={`${r.filename ?? r.dataset}-${i}`}
                className="rounded-md border px-3 py-2 text-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate">{r.filename ?? '—'}</span>
                  <Badge variant="outline">{r.dataset}</Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t('market.gold.import.result_rows', {
                    imported: Number(r.rows_imported).toLocaleString(),
                    skipped: Number(r.rows_skipped).toLocaleString(),
                    codes: Number(r.codes).toLocaleString(),
                  })}
                </p>
                {r.errors.length > 0 && (
                  <ul className="mt-1 list-inside list-disc text-xs text-destructive">
                    {r.errors.map((err) => (
                      <li key={err}>{err}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            {t('common.close')}
          </Button>
          <Button onClick={onImport} disabled={files.length === 0 || importMutation.isPending}>
            {importMutation.isPending && <Loader2 className="animate-spin" />}
            {t('market.gold.import.submit')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
