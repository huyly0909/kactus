import { type FC } from 'react';
import { Outlet } from 'react-router-dom';
import { useAuthStore } from '@kactus-bloom/ui/stores';
import { NotFoundPage } from '../pages/NotFound';

/**
 * Admin guard — only allows superusers to access admin routes.
 * Non-superusers see the 404 page (URL stays at /admin/*).
 */
export const AdminGuard: FC = () => {
  const { user, isAuthenticated } = useAuthStore();

  if (!isAuthenticated || !user?.is_superuser) {
    return <NotFoundPage />;
  }

  return <Outlet />;
};
