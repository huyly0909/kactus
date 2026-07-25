import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Briefcase, Bell, BellRing, ArrowRight } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { usePortfolios } from '@/hooks/usePortfolioQuery';
import { useNotificationChannels } from '@/hooks/useNotificationQuery';

interface StatProps {
  icon: React.ElementType;
  label: string;
  value: number | string;
  loading?: boolean;
}

function Stat({ icon: Icon, label, value, loading }: StatProps) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          {loading ? (
            <Skeleton className="mt-1 h-6 w-10" />
          ) : (
            <p className="text-2xl font-bold tabular-nums">{value}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: portfolios, isLoading: pfLoading } = usePortfolios();
  const { data: channels, isLoading: chLoading } = useNotificationChannels();

  const activeChannels = channels?.filter((c) => c.is_active).length ?? 0;
  const recent = portfolios?.slice(0, 5) ?? [];

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">{t('dashboard.title')}</h1>
        <p className="text-sm text-muted-foreground">{t('dashboard.subtitle')}</p>
      </div>

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Stat
          icon={Briefcase}
          label={t('dashboard.stat_portfolios')}
          value={portfolios?.length ?? 0}
          loading={pfLoading}
        />
        <Stat
          icon={Bell}
          label={t('dashboard.stat_channels')}
          value={channels?.length ?? 0}
          loading={chLoading}
        />
        <Stat
          icon={BellRing}
          label={t('dashboard.stat_active_channels')}
          value={activeChannels}
          loading={chLoading}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">{t('dashboard.recent_portfolios')}</CardTitle>
            <Button variant="ghost" size="sm" onClick={() => navigate('/portfolios')}>
              {t('dashboard.view_all')}
              <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </CardHeader>
          <CardContent className="space-y-1">
            {pfLoading && <Skeleton className="h-24 w-full" />}
            {!pfLoading && recent.length === 0 && (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {t('portfolio.empty_list')}
              </p>
            )}
            {recent.map((p) => (
              <button
                key={p.id}
                onClick={() => navigate(`/portfolios/${p.id}`)}
                className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-accent"
              >
                <span className="truncate font-medium">{p.name}</span>
                <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
              </button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t('dashboard.quick_actions')}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <Button
              variant="outline"
              className="justify-start"
              onClick={() => navigate('/portfolios')}
            >
              <Briefcase className="mr-2 h-4 w-4" />
              {t('nav.portfolios')}
            </Button>
            <Button
              variant="outline"
              className="justify-start"
              onClick={() => navigate('/notifications')}
            >
              <Bell className="mr-2 h-4 w-4" />
              {t('nav.notifications')}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
