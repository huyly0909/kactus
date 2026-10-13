import { type FC } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Coins, Database, LineChart, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import { GoldOverviewPane } from '@modules/market/components/GoldOverviewPane';
import { GoldDataPane } from '@modules/market/components/GoldDataPane';

type TabId = 'overview' | 'data';

interface TabDef {
  id: TabId;
  icon: LucideIcon;
  labelKey: string;
  /** Superuser-only (backfill / sync-now write the single DuckDB handle). */
  superuser?: boolean;
  Pane: FC;
}

const TABS: TabDef[] = [
  {
    id: 'overview',
    icon: LineChart,
    labelKey: 'market.gold.tabs.overview',
    Pane: GoldOverviewPane,
  },
  {
    id: 'data',
    icon: Database,
    labelKey: 'market.gold.tabs.data',
    superuser: true,
    Pane: GoldDataPane,
  },
];

/**
 * Gold page shell — routes `market/gold/:tab` to the Overview board or the
 * superuser Data tab (backfill + sync-now), mirroring the settings `:tab`
 * idiom. An unknown or unauthorised tab falls back to Overview.
 */
export const GoldPricesPage: FC = () => {
  const { t } = useTranslation();
  const { tab } = useParams<{ tab: string }>();
  const { user } = useAuth();

  const visibleTabs = TABS.filter((x) => !x.superuser || user?.is_superuser);
  const active = visibleTabs.find((x) => x.id === tab);
  if (!active) return <Navigate to="/market/gold/overview" replace />;
  const ActivePane = active.Pane;

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-[var(--warning)]/15 text-[var(--warning)]">
          <Coins className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{t('market.gold.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('market.gold.subtitle')}</p>
        </div>
      </div>

      <div className="mb-6 flex gap-1 border-b border-border">
        {visibleTabs.map((x) => {
          const Icon = x.icon;
          const isActive = active.id === x.id;
          return (
            <Link
              key={x.id}
              to={`/market/gold/${x.id}`}
              className={cn(
                'flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              )}
            >
              <Icon className="h-4 w-4" />
              {t(x.labelKey)}
            </Link>
          );
        })}
      </div>

      <ActivePane />
    </div>
  );
};
