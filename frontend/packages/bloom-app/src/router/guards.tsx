import { type FC, useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@kactus-bloom/ui/hooks';
import { Center, Loader } from '@mantine/core';

/**
 * Auth guard — checks session cookie via /api/auth/me on mount.
 * Shows loader while checking, redirects to /login if unauthenticated.
 */
export const AuthGuard: FC = () => {
  const { isAuthenticated, isLoading, checkSession } = useAuth();
  const location = useLocation();

  useEffect(() => {
    checkSession();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (isLoading) {
    return (
      <Center h="100vh">
        <Loader size="lg" />
      </Center>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
};
