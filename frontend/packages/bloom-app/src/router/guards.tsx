import { type FC } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '@kactus-bloom/ui/stores';

/**
 * Auth guard — redirects unauthenticated users to /login.
 * Wraps protected routes via <Outlet />.
 */
export const AuthGuard: FC = () => {
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
    const location = useLocation();

    if (!isAuthenticated) {
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return <Outlet />;
};
