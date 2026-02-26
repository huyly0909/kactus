import { type FC, useMemo } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Badge } from '@mantine/core';
import {
  FolderOpen,
  LayoutDashboard,
  FileText,
  Settings,
  Shield,
  ArrowRightLeft,
} from 'lucide-react';
import { AppLayout } from '@kactus-bloom/ui';
import { useAuth } from '@kactus-bloom/ui/hooks';
import { useProjectStore, useAuthStore } from '@kactus-bloom/ui/stores';

/**
 * User-facing layout for all non-admin authenticated pages.
 *
 * Sidebar behavior:
 * - No project selected: shows "Select Project"
 * - Project selected (cookie or store): shows Dashboard, Reports, Settings, Switch Project
 * - Superuser: shows "Admin Panel" link
 *
 * NOTE: We check the cookie synchronously to decide sidebar items.
 * ProjectGuard handles the actual project data restoration.
 */
export const MainLayout: FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout } = useAuth();
  const { user } = useAuthStore();
  const { currentProject, clearProject, getProjectIdFromCookie } = useProjectStore();

  const isSuperuser = user?.is_superuser ?? false;

  // Check cookie synchronously — no API call needed for sidebar decisions
  const hasProjectCookie = !!getProjectIdFromCookie();
  const hasProject = !!currentProject || hasProjectCookie;

  const navSections = useMemo(() => {
    const sections = [];

    if (hasProject) {
      // Project is selected — show project-scoped items
      sections.push({
        items: [
          { label: 'Dashboard', icon: <LayoutDashboard size={18} />, href: '/dashboard' },
          { label: 'Reports', icon: <FileText size={18} />, href: '/reports' },
          { label: 'Settings', icon: <Settings size={18} />, href: '/settings' },
          { label: 'Switch Project', icon: <ArrowRightLeft size={18} />, href: '/select-project' },
        ],
      });
    } else {
      // No project — show Select Project
      sections.push({
        items: [
          { label: 'Select Project', icon: <FolderOpen size={18} />, href: '/select-project' },
        ],
      });
    }

    // Admin link for superusers
    if (isSuperuser) {
      sections.push({
        label: 'Admin',
        items: [{ label: 'Admin Panel', icon: <Shield size={18} />, href: '/admin' }],
      });
    }

    return sections;
  }, [hasProject, isSuperuser]);

  const handleLogout = async () => {
    clearProject();
    await logout();
    navigate('/login');
  };

  return (
    <AppLayout
      title="Kactus Bloom"
      navSections={navSections}
      currentPath={location.pathname}
      headerRight={
        currentProject ? (
          <Badge
            variant="light"
            color="blue"
            size="lg"
            style={{ cursor: 'pointer' }}
            onClick={() => navigate('/select-project')}
          >
            {currentProject.name}
          </Badge>
        ) : undefined
      }
      onNavigate={(href) => navigate(href)}
      onLogout={handleLogout}
    >
      <Outlet />
    </AppLayout>
  );
};
