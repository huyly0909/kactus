import { Suspense, useLayoutEffect, useRef } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { BreadcrumbScopeProvider } from '@/layouts/components/BreadcrumbScope';
import { ModuleSidebar } from '@/layouts/components/ModuleSidebar';
import { TopHeader } from '@/layouts/components/TopHeader';

/**
 * App shell — registry-driven sidebar (mega-menu on hover / accordion on touch /
 * drawer on mobile) + breadcrumb header. Lazy pages load behind the <Suspense>.
 *
 * `main` is the one scrollport: pages grow inside it and any sticky page header
 * pins against it, not against the viewport.
 */
export function DashboardLayout() {
  const { pathname } = useLocation();
  const mainRef = useRef<HTMLElement>(null);

  // `main` keeps its scrollTop across route changes. Harmless on a plain page,
  // but with a sticky page header you land mid-document with the header pinned,
  // which reads as a broken render.
  useLayoutEffect(() => {
    mainRef.current?.scrollTo({ top: 0 });
  }, [pathname]);

  return (
    <BreadcrumbScopeProvider>
      <div className="flex h-dvh overflow-hidden bg-background">
        <ModuleSidebar />
        <div className="flex flex-1 flex-col min-w-0">
          <TopHeader />
          <main ref={mainRef} className="flex-1 overflow-y-auto">
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
