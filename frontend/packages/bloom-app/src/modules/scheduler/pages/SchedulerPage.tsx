import { type FC } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { CalendarClock, ListChecks, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import { SchedulerJobsPane } from '@modules/scheduler/components/SchedulerJobsPane';
import { SchedulerQueuePane } from '@modules/scheduler/components/SchedulerQueuePane';

type TabId = 'jobs' | 'queue';

interface TabDef {
  id: TabId;
  icon: LucideIcon;
  labelKey: string;
  Pane: FC;
}

const TABS: TabDef[] = [
  { id: 'jobs', icon: CalendarClock, labelKey: 'scheduler.tab.jobs', Pane: SchedulerJobsPane },
  { id: 'queue', icon: ListChecks, labelKey: 'scheduler.tab.queue', Pane: SchedulerQueuePane },
];

/**
 * Scheduler page shell — routes `scheduler/:tab` to the recurring-jobs view or
 * the shared sync queue, mirroring the gold/settings `:tab` idiom. Superuser
 * only (both tabs read admin endpoints). Unknown tab → Jobs.
 */
export const SchedulerPage: FC = () => {
  const { t } = useTranslation();
  const { tab } = useParams<{ tab: string }>();
  const { user } = useAuth();

  if (!user?.is_superuser) return <Navigate to="/" replace />;
  const active = TABS.find((x) => x.id === tab);
  if (!active) return <Navigate to="/scheduler/jobs" replace />;
  const ActivePane = active.Pane;

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary/15 text-primary">
          <CalendarClock className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{t('scheduler.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('scheduler.subtitle')}</p>
        </div>
      </div>

      <div className="mb-6 flex gap-1 border-b border-border">
        {TABS.map((x) => {
          const Icon = x.icon;
          const isActive = active.id === x.id;
          return (
            <Link
              key={x.id}
              to={`/scheduler/${x.id}`}
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
