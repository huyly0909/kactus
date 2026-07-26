import { Suspense } from 'react';
import { Outlet } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { BreadcrumbScopeProvider } from '@/layouts/components/BreadcrumbScope';
import { ModuleSidebar } from '@/layouts/components/ModuleSidebar';
import { TopHeader } from '@/layouts/components/TopHeader';

/**
 * App shell — registry-driven sidebar (mega-menu on hover / accordion on touch /
 * drawer on mobile) + breadcrumb header. Lazy pages load behind the <Suspense>.
 */
export function DashboardLayout() {
  return (
    <BreadcrumbScopeProvider>
      <div className="flex h-dvh overflow-hidden bg-background">
        <ModuleSidebar />
        <div className="flex flex-1 flex-col min-w-0">
          <TopHeader />
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
    </BreadcrumbScopeProvider>
  );
}
