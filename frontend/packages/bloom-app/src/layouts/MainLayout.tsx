import { type FC } from 'react';
import { Outlet } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';
import { AppLayout } from '@kactus-bloom/ui';
import { useAuth } from '@kactus-bloom/ui/hooks';

/**
 * Main layout for authenticated pages — sidebar + header + content.
 */
export const MainLayout: FC = () => {
    const navigate = useNavigate();
    const { logout } = useAuth();

    const handleNavigate = (href: string) => {
        navigate(href);
    };

    const handleLogout = async () => {
        await logout();
        navigate('/login');
    };

    return (
        <AppLayout onNavigate={handleNavigate} onLogout={handleLogout}>
            <Outlet />
        </AppLayout>
    );
};
