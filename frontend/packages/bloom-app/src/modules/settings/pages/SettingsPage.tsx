import { type FC } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { User, Users, FolderKanban, Palette, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useIsAdmin } from '@/hooks/useIsAdmin';
import { ProfilePane } from '@modules/settings/components/ProfilePane';
import { PreferencesPane } from '@modules/settings/components/PreferencesPane';
import { UsersPane } from '@modules/settings/components/UsersPane';
import { ProjectsPane } from '@modules/settings/components/ProjectsPane';

type TabId = 'profile' | 'users' | 'projects' | 'preferences';

interface TabDef {
  id: TabId;
  icon: LucideIcon;
  labelKey: string;
  admin?: boolean;
  Pane: FC;
}

const TABS: TabDef[] = [
  { id: 'profile', icon: User, labelKey: 'settings.profile', Pane: ProfilePane },
  { id: 'users', icon: Users, labelKey: 'settings.users', admin: true, Pane: UsersPane },
  {
    id: 'projects',
    icon: FolderKanban,
    labelKey: 'settings.projects',
    admin: true,
    Pane: ProjectsPane,
  },
  { id: 'preferences', icon: Palette, labelKey: 'settings.preferences', Pane: PreferencesPane },
];

export const SettingsPage: FC = () => {
  const { t } = useTranslation();
  const { tab } = useParams<{ tab: string }>();
  const isAdmin = useIsAdmin();

  const visibleTabs = TABS.filter((x) => !x.admin || isAdmin);
  const active = visibleTabs.find((x) => x.id === tab) ?? visibleTabs[0];
  const ActivePane = active.Pane;

  return (
    <div className="flex h-full min-h-0 flex-col bg-background md:flex-row">
      <aside className="shrink-0 border-b border-border/40 md:w-60 md:border-b-0 md:border-r">
        <nav className="scrollbar-hide flex gap-0.5 overflow-x-auto p-2 md:flex-col md:overflow-y-auto">
          {visibleTabs.map((x) => {
            const Icon = x.icon;
            const isActive = active.id === x.id;
            return (
              <Link
                key={x.id}
                to={`/settings/${x.id}`}
                className={cn(
                  'group flex cursor-pointer items-center gap-2.5 whitespace-nowrap rounded-md px-3 py-2 text-sm outline-none transition-all duration-150 ease-in-out active:scale-[0.98] md:w-full',
                  isActive
                    ? 'bg-primary/10 font-semibold text-primary dark:bg-primary/20'
                    : 'font-medium text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                )}
              >
                <Icon
                  className={cn(
                    'h-[18px] w-[18px] shrink-0',
                    !isActive && 'opacity-80 group-hover:opacity-100',
                  )}
                />
                <span className="truncate">{t(x.labelKey)}</span>
              </Link>
            );
          })}
        </nav>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto">
        <ActivePane />
      </main>
    </div>
  );
};
