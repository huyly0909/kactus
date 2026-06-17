import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Plus, Briefcase } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { usePortfolios } from '@/hooks/usePortfolioQuery';
import { CreatePortfolioDialog } from '@modules/portfolio/components/CreatePortfolioDialog';

export function PortfolioListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: portfolios, isLoading } = usePortfolios();
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('portfolio.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('portfolio.subtitle')}</p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="mr-1 h-4 w-4" />
          {t('portfolio.create_title')}
        </Button>
      </div>

      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      )}

      {!isLoading && (portfolios?.length ?? 0) === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16 text-center">
          <Briefcase className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{t('portfolio.empty_list')}</p>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {portfolios?.map((p) => (
          <Card
            key={p.id}
            className="cursor-pointer transition-colors hover:border-primary/50"
            onClick={() => navigate(`/portfolios/${p.id}`)}
          >
            <CardHeader>
              <CardTitle className="text-base">{p.name}</CardTitle>
              {p.description && <CardDescription>{p.description}</CardDescription>}
            </CardHeader>
            <CardContent className="text-xs text-muted-foreground">
              {t('portfolio.open_detail')}
            </CardContent>
          </Card>
        ))}
      </div>

      <CreatePortfolioDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
