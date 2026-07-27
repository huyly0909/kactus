import { lazy, useEffect } from 'react';
import { createBrowserRouter, RouterProvider, Routes, Route, Navigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useThemeStore } from '@/store/themeStore';
import { useDebugUrlSync } from '@/hooks/useDebugMode';
import { DashboardLayout } from '@/layouts/DashboardLayout';
import { NotFoundRedirect } from '@/layouts/components/NotFoundRedirect';
import { LoginPage } from '@/modules/core/auth/pages/LoginPage';

// Route-level code splitting — each page becomes its own async chunk, loaded on
// demand behind the DashboardLayout's <Suspense> boundary (named → default).
const DashboardPage = lazy(() =>
  import('@/modules/core/dashboard/pages/DashboardPage').then((m) => ({
    default: m.DashboardPage,
  })),
);
const ProjectListPage = lazy(() =>
  import('@modules/project/pages/ProjectListPage').then((m) => ({
    default: m.ProjectListPage,
  })),
);
const ProjectDetailPage = lazy(() =>
  import('@modules/project/pages/ProjectDetailPage').then((m) => ({
    default: m.ProjectDetailPage,
  })),
);
const PortfolioListPage = lazy(() =>
  import('@modules/portfolio/pages/PortfolioListPage').then((m) => ({
    default: m.PortfolioListPage,
  })),
);
const PortfolioDetailPage = lazy(() =>
  import('@modules/portfolio/pages/PortfolioDetailPage').then((m) => ({
    default: m.PortfolioDetailPage,
  })),
);
const NotificationListPage = lazy(() =>
  import('@modules/notification/pages/NotificationListPage').then((m) => ({
    default: m.NotificationListPage,
  })),
);
const NotificationDetailPage = lazy(() =>
  import('@modules/notification/pages/NotificationDetailPage').then((m) => ({
    default: m.NotificationDetailPage,
  })),
);
const GoldPricesPage = lazy(() =>
  import('@modules/market/pages/GoldPricesPage').then((m) => ({ default: m.GoldPricesPage })),
);
const SyncQueuePage = lazy(() =>
  import('@modules/market/pages/SyncQueuePage').then((m) => ({ default: m.SyncQueuePage })),
);
const StockMarketPage = lazy(() =>
  import('@modules/market/pages/StockMarketPage').then((m) => ({ default: m.StockMarketPage })),
);
const StockDetailPage = lazy(() =>
  import('@modules/market/pages/StockDetailPage').then((m) => ({ default: m.StockDetailPage })),
);
const FinancePage = lazy(() =>
  import('@modules/market/pages/FinancePage').then((m) => ({ default: m.FinancePage })),
);
const FinanceReportPage = lazy(() =>
  import('@modules/market/pages/FinanceReportPage').then((m) => ({
    default: m.FinanceReportPage,
  })),
);
const SettingsPage = lazy(() =>
  import('@modules/settings/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })),
);

/**
 * App shell — mirrors Builtiful's App.tsx pattern:
 * 1. Check session on mount
 * 2. Show loader while checking
 * 3. Show login if no user
 * 4. Show router if authenticated
 */
function AppRoutes() {
  useDebugUrlSync();
  return (
    <Routes>
      <Route path="/" element={<DashboardLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="projects" element={<ProjectListPage />} />
        <Route path="projects/:id" element={<ProjectDetailPage />} />
        <Route path="portfolios" element={<PortfolioListPage />} />
        <Route path="portfolios/:id" element={<PortfolioDetailPage />} />
        <Route path="notifications" element={<NotificationListPage />} />
        <Route path="notifications/:id" element={<NotificationDetailPage />} />
        {/* Market module root → its first sub-page (the sidebar trigger links here). */}
        <Route path="market" element={<Navigate to="/market/gold/overview" replace />} />
        {/* Gold: Overview (board) + Data (superuser backfill/sync), tab in the URL. */}
        <Route path="market/gold" element={<Navigate to="/market/gold/overview" replace />} />
        <Route path="market/gold/:tab" element={<GoldPricesPage />} />
        {/* Shared sync-job queue (superuser) — gold's backfill/sync jobs run here. */}
        <Route path="market/sync" element={<SyncQueuePage />} />
        <Route path="market/stocks" element={<StockMarketPage />} />
        <Route path="market/stocks/:symbol" element={<StockDetailPage />} />
        <Route path="market/finance" element={<FinancePage />} />
        {/* POC — the finance pivot rebuilt on the ReportView primitive. */}
        <Route path="market/finance-report" element={<FinanceReportPage />} />
        {/* Admin (Users/Projects) folded into Settings. Old links redirect. */}
        <Route path="admin" element={<Navigate to="/settings/users" replace />} />
        <Route path="admin/users" element={<Navigate to="/settings/users" replace />} />
        <Route path="admin/authorization" element={<Navigate to="/settings/users" replace />} />
        <Route path="admin/projects" element={<Navigate to="/settings/projects" replace />} />
        {/* Settings — not a registry module; reached from the sidebar/header. */}
        <Route path="settings" element={<Navigate to="/settings/profile" replace />} />
        <Route
          path="settings/appearance"
          element={<Navigate to="/settings/preferences" replace />}
        />
        <Route path="settings/:tab" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundRedirect />} />
      </Route>
    </Routes>
  );
}

const router = createBrowserRouter([{ path: '*', element: <AppRoutes /> }]);

function App() {
  const { user, isLoading, checkSession } = useAuth();
  const mode = useThemeStore((s) => s.mode);
  const color = useThemeStore((s) => s.color);
  const radius = useThemeStore((s) => s.radius);
  const scale = useThemeStore((s) => s.scale);

  useEffect(() => {
    void checkSession();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Reflect the theme axes onto <html>. Clears prior atoms by prefix so we never
  // drift out of sync with the preset list in index.css; `default` color adds no
  // `theme-*` class (keeps the indigo base), `dark` mode adds no class (base).
  useEffect(() => {
    const root = document.documentElement;
    Array.from(root.classList)
      .filter(
        (cls) =>
          cls === 'light' ||
          cls.startsWith('theme-') ||
          cls.startsWith('radius-') ||
          cls.startsWith('scale-'),
      )
      .forEach((cls) => root.classList.remove(cls));

    if (mode === 'light') root.classList.add('light');
    if (color !== 'default') root.classList.add(`theme-${color}`);
    root.classList.add(`radius-${radius}`, `scale-${scale}`);
  }, [mode, color, radius, scale]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="min-h-screen bg-background transition-colors duration-200">
      <RouterProvider router={router} />
    </div>
  );
}

export default App;
