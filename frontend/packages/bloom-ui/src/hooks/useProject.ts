import { useProjectStore } from '../stores/projectStore';
import { projectService } from '../services/projectService';
import type { Project } from '../types/project';

interface UseProjectReturn {
  currentProject: Project | null;
  isLoading: boolean;
  selectProject: (project: Project) => void;
  clearProject: () => void;
  getProjectIdFromCookie: () => string | undefined;
  loadProjectFromCookie: () => Promise<void>;
}

/**
 * Project hook — wraps projectStore + projectService for convenience.
 */
export const useProject = (): UseProjectReturn => {
  const {
    currentProject,
    isLoading,
    setProject,
    clearProject,
    setLoading,
    getProjectIdFromCookie,
  } = useProjectStore();

  const selectProject = (project: Project) => {
    setProject(project);
  };

  /** Restore project from cookie on app mount. */
  const loadProjectFromCookie = async () => {
    const projectId = getProjectIdFromCookie();
    if (!projectId) return;

    if (currentProject && currentProject.id === projectId) return;

    setLoading(true);
    try {
      const project = await projectService.getProjectById(projectId);
      setProject(project);
    } catch {
      clearProject();
    }
  };

  return {
    currentProject,
    isLoading,
    selectProject,
    clearProject,
    getProjectIdFromCookie,
    loadProjectFromCookie,
  };
};
