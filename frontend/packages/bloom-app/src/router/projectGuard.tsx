import { type FC, useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { Center, Loader } from '@mantine/core';
import { useProjectStore } from '@kactus-bloom/ui/stores';
import { projectService } from '@kactus-bloom/ui/services';

/**
 * Project guard — ensures a project is selected before accessing protected routes.
 * If no project is selected (no cookie), redirects to /select-project.
 *
 * Uses the list endpoint (GET /api/projects) to restore the project from cookie,
 * avoiding the @permission-protected single-project endpoint.
 */
export const ProjectGuard: FC = () => {
  const {
    currentProject,
    isLoading,
    setProject,
    clearProject,
    setLoading,
    getProjectIdFromCookie,
  } = useProjectStore();
  const location = useLocation();

  useEffect(() => {
    const restoreProject = async () => {
      const projectId = getProjectIdFromCookie();
      if (!projectId) {
        setLoading(false);
        return;
      }

      if (currentProject && currentProject.id === projectId) {
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const { items } = await projectService.getProjects();
        const project = items.find((p) => String(p.id) === String(projectId));
        if (project) {
          setProject(project);
        } else {
          // Cookie references a project the user is not a member of — clear it
          clearProject();
        }
      } catch {
        clearProject();
      }
    };
    restoreProject();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (isLoading) {
    return (
      <Center h="100vh">
        <Loader size="lg" />
      </Center>
    );
  }

  const projectId = getProjectIdFromCookie();
  if (!projectId && !currentProject) {
    return <Navigate to="/select-project" state={{ from: location }} replace />;
  }

  return <Outlet />;
};
