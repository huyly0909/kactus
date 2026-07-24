import { type FC, type ReactNode } from 'react';
import { LogOut } from 'lucide-react';
import { cn } from '../../lib/utils';

interface NavItem {
  label: string;
  icon: ReactNode;
  href: string;
}

interface NavSection {
  label?: string;
  items: NavItem[];
}

interface AppLayoutProps {
  children: ReactNode;
  /** Title shown in the header. */
  title?: string;
  /** Sections of nav items to display in the sidebar. */
  navSections: NavSection[];
  /** Current pathname for active-item highlighting. */
  currentPath?: string;
  /** Optional extra content in the header (right side). */
  headerRight?: ReactNode;
  onNavigate?: (href: string) => void;
  onLogout?: () => void;
}

/**
 * Generic application shell — sidebar + header + content area.
 * shadcn/Tailwind port (previously Mantine `AppShell`). Prop-driven so each
 * layout (Admin, User) composes it with its own nav sections.
 */
export const AppLayout: FC<AppLayoutProps> = ({
  children,
  title = 'Kactus Bloom',
  navSections,
  currentPath = '',
  headerRight,
  onNavigate,
  onLogout,
}) => {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <aside className="flex w-64 flex-col border-r border-border bg-sidebar">
        <div className="flex h-14 items-center border-b border-border px-4">
          <span className="text-lg font-bold tracking-tight text-foreground">{title}</span>
        </div>

        <nav className="flex-1 space-y-4 overflow-y-auto p-3">
          {navSections.map((section, idx) => (
            <div key={section.label ?? idx} className="space-y-1">
              {section.label && (
                <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {section.label}
                </p>
              )}
              {section.items.map((item) => (
                <button
                  key={item.href}
                  onClick={() => onNavigate?.(item.href)}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    currentPath === item.href
                      ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                      : 'text-sidebar-foreground hover:bg-sidebar-accent/50',
                  )}
                >
                  <span className="shrink-0">{item.icon}</span>
                  <span className="truncate">{item.label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="border-t border-border p-3">
          <button
            onClick={onLogout}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center justify-between border-b border-border px-6">
          <div />
          {headerRight}
        </header>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
};
