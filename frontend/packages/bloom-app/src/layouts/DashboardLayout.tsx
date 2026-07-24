import { Suspense, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  LayoutDashboard,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  User,
  Briefcase,
  Bell,
  Loader2,
  Users,
  FolderKanban,
  ShieldCheck,
  Coins,
  LineChart,
  FileSpreadsheet,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';

interface SidebarItem {
  id: string;
  labelKey: string;
  icon: React.ElementType;
  path: string;
  /** Only rendered for superusers. */
  adminOnly?: boolean;
}

const SIDEBAR_ITEMS: SidebarItem[] = [
  { id: 'dashboard', labelKey: 'nav.dashboard', icon: LayoutDashboard, path: '/' },
  { id: 'portfolios', labelKey: 'nav.portfolios', icon: Briefcase, path: '/portfolios' },
  { id: 'notifications', labelKey: 'nav.notifications', icon: Bell, path: '/notifications' },
  { id: 'gold', labelKey: 'nav.gold', icon: Coins, path: '/market/gold' },
  { id: 'stocks', labelKey: 'nav.stock', icon: LineChart, path: '/market/stocks' },
  { id: 'finance', labelKey: 'nav.finance', icon: FileSpreadsheet, path: '/market/finance' },
];

const ADMIN_ITEMS: SidebarItem[] = [
  { id: 'admin-users', labelKey: 'nav.users', icon: Users, path: '/admin/users', adminOnly: true },
  {
    id: 'admin-projects',
    labelKey: 'nav.projects',
    icon: FolderKanban,
    path: '/admin/projects',
    adminOnly: true,
  },
  {
    id: 'admin-authorization',
    labelKey: 'nav.authorization',
    icon: ShieldCheck,
    path: '/admin/authorization',
    adminOnly: true,
  },
];

export function DashboardLayout() {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const renderNavItem = (item: SidebarItem) => {
    const isActive =
      location.pathname === item.path ||
      (item.path !== '/' && location.pathname.startsWith(item.path));
    const Icon = item.icon;
    return (
      <button
        key={item.id}
        onClick={() => {
          navigate(item.path);
          setMobileOpen(false);
        }}
        className={cn(
          'flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
          isActive
            ? 'bg-sidebar-accent text-sidebar-accent-foreground'
            : 'text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
          collapsed && 'justify-center px-2',
        )}
      >
        <Icon className="h-4 w-4 shrink-0" />
        {!collapsed && <span className="truncate">{t(item.labelKey)}</span>}
      </button>
    );
  };

  const handleLogout = async () => {
    await logout();
    window.location.href = '/login';
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'flex flex-col border-r border-sidebar-border bg-sidebar transition-all duration-200',
          collapsed ? 'w-16' : 'w-60',
          // Mobile: absolute overlay
          'fixed inset-y-0 left-0 z-50 md:relative',
          mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
        )}
      >
        {/* Header */}
        <div
          className={cn(
            'flex h-14 items-center border-b border-sidebar-border px-4',
            collapsed ? 'justify-center' : 'justify-between',
          )}
        >
          {!collapsed && (
            <span className="text-lg font-bold text-foreground tracking-tight">Kactus</span>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="hidden md:flex text-sidebar-foreground hover:text-foreground"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden text-sidebar-foreground"
            onClick={() => setMobileOpen(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 p-2 overflow-y-auto">
          {SIDEBAR_ITEMS.map(renderNavItem)}

          {/* Admin section — superusers only */}
          {user?.is_superuser && (
            <>
              <div className="my-2 border-t border-sidebar-border pt-2">
                {!collapsed && (
                  <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {t('nav.admin')}
                  </p>
                )}
              </div>
              {ADMIN_ITEMS.map(renderNavItem)}
            </>
          )}
        </nav>

        {/* Footer — user + logout */}
        <div className="border-t border-sidebar-border p-2">
          {!collapsed && user && (
            <div className="flex items-center gap-3 px-3 py-2 mb-1">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-semibold">
                {user.name?.charAt(0)?.toUpperCase() || <User className="h-4 w-4" />}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{user.name}</p>
                <p className="text-xs text-muted-foreground truncate">{user.email}</p>
              </div>
            </div>
          )}
          <button
            onClick={handleLogout}
            className={cn(
              'flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-sidebar-foreground hover:bg-destructive/10 hover:text-destructive transition-colors',
              collapsed && 'justify-center px-2',
            )}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {!collapsed && <span>{t('auth.logout')}</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Top header (mobile) */}
        <header className="flex h-14 items-center gap-4 border-b border-border px-4 md:hidden">
          <Button variant="ghost" size="icon" onClick={() => setMobileOpen(true)}>
            <Menu className="h-5 w-5" />
          </Button>
          <span className="text-lg font-bold tracking-tight">Kactus</span>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center py-24">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            }
          >
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
