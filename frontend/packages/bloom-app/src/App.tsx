import { lazy, useEffect } from 'react';
import { createBrowserRouter, RouterProvider, Routes, Route } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { DashboardLayout } from '@/layouts/DashboardLayout';
import { LoginPage } from '@/modules/core/auth/pages/LoginPage';

// Route-level code splitting — each page becomes its own async chunk, loaded on
// demand behind the DashboardLayout's <Suspense> boundary (named → default).
const DashboardPage = lazy(() =>
  import('@/modules/core/dashboard/pages/DashboardPage').then((m) => ({
    default: m.DashboardPage,
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

/**
 * App shell — mirrors Builtiful's App.tsx pattern:
 * 1. Check session on mount
 * 2. Show loader while checking
 * 3. Show login if no user
 * 4. Show router if authenticated
 */
function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<DashboardLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="portfolios" element={<PortfolioListPage />} />
        <Route path="portfolios/:id" element={<PortfolioDetailPage />} />
        <Route path="notifications" element={<NotificationListPage />} />
        <Route path="notifications/:id" element={<NotificationDetailPage />} />
        <Route path="*" element={<div className="p-8 text-muted-foreground">Page not found</div>} />
      </Route>
    </Routes>
  );
}

const router = createBrowserRouter([{ path: '*', element: <AppRoutes /> }]);

function App() {
  const { user, isLoading, checkSession } = useAuth();

  useEffect(() => {
    void checkSession();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
