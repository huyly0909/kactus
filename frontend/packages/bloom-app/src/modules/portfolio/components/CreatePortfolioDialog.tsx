import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useCreatePortfolio } from '@/hooks/usePortfolioQuery';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Minimal modal (no extra deps) for creating a portfolio. */
export function CreatePortfolioDialog({ open, onOpenChange }: Props) {
  const { t } = useTranslation();
  const create = useCreatePortfolio();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    await create.mutateAsync({ name: name.trim(), description: description.trim() || undefined });
    setName('');
    setDescription('');
    onOpenChange(false);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t('portfolio.create_title')}</h2>
          <Button variant="ghost" size="icon" onClick={() => onOpenChange(false)}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="pf-name">{t('portfolio.name')}</Label>
            <Input
              id="pf-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('portfolio.name_placeholder')}
              autoFocus
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="pf-desc">{t('portfolio.description')}</Label>
            <Input
              id="pf-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" disabled={create.isPending || !name.trim()}>
              {t('common.create')}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
