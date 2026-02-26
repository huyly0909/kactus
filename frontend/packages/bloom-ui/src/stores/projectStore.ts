import Cookies from 'js-cookie';
import { create } from 'zustand';
import type { Project } from '../types/project';

const PROJECT_COOKIE_NAME = 'kactus_project_id';

interface ProjectState {
  currentProject: Project | null;
  isLoading: boolean;
  setProject: (project: Project) => void;
  clearProject: () => void;
  setLoading: (loading: boolean) => void;
  getProjectIdFromCookie: () => string | undefined;
}

/**
 * Project store — tracks the currently selected project.
 * Project ID is persisted in a cookie for API requests.
 */
export const useProjectStore = create<ProjectState>((set) => ({
  currentProject: null,
  isLoading: false,

  setProject: (project) => {
    Cookies.set(PROJECT_COOKIE_NAME, project.id, { expires: 365 });
    set({ currentProject: project, isLoading: false });
  },

  clearProject: () => {
    Cookies.remove(PROJECT_COOKIE_NAME);
    set({ currentProject: null, isLoading: false });
  },

  setLoading: (isLoading) => set({ isLoading }),

  getProjectIdFromCookie: () => Cookies.get(PROJECT_COOKIE_NAME),
}));
