import { type FC } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Button } from '@mantine/core';
import { Users, FolderCog, Shield, ArrowLeft } from 'lucide-react';
import { AppLayout } from '@kactus-bloom/ui';
import { useAuth } from '@kactus-bloom/ui/hooks';
import { useProjectStore } from '@kactus-bloom/ui/stores';

const adminSections = [
  {
    items: [
      { label: 'Users', icon: <Users size={18} />, href: '/admin/users' },
      { label: 'Projects', icon: <FolderCog size={18} />, href: '/admin/projects' },
      { label: 'Authorization', icon: <Shield size={18} />, href: '/admin/authorization' },
    ],
  },
];

/**
 * Admin layout — separate from the user layout.
 * Sidebar: Users, Projects, Authorization.
 * No project selection needed.
 */
export const AdminLayout: FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout } = useAuth();
  const { clearProject } = useProjectStore();

  const handleLogout = async () => {
    clearProject();
    await logout();
    navigate('/login');
  };

  return (
    <AppLayout
      title="Admin Panel"
      navSections={adminSections}
      currentPath={location.pathname}
      headerRight={
        <Button
          variant="subtle"
          size="xs"
          leftSection={<ArrowLeft size={14} />}
          onClick={() => navigate('/select-project')}
        >
          Back to App
        </Button>
      }
      onNavigate={(href) => navigate(href)}
      onLogout={handleLogout}
    >
      <Outlet />
    </AppLayout>
  );
};
