import Cookies from 'js-cookie';
import { create } from 'zustand';
import type { Project } from '../types/project';

const PROJECT_COOKIE_NAME = 'kactus_project_id';

interface ProjectState {
  currentProject: Project | null;
  isLoading: boolean;
  /** False until `hydrateActiveProject` has resolved on this page load. */
  hydrated: boolean;
  setProject: (project: Project) => void;
  clearProject: () => void;
  setLoading: (loading: boolean) => void;
  setHydrated: (hydrated: boolean) => void;
  getProjectIdFromCookie: () => string | undefined;
}

/**
 * Project store — tracks the currently selected project.
 * Project ID is persisted in a cookie for API requests.
 *
 * Not persisted: `currentProject` is `null` on every page load until
 * `hydrateActiveProject` resolves it from the cookie + memberships. `hydrated`
 * is what separates "no project" from "not known yet" — without it, guards read
 * the initial `null` and redirect before the answer arrives.
 */
export const useProjectStore = create<ProjectState>((set) => ({
  currentProject: null,
  isLoading: false,
  hydrated: false,

  setProject: (project) => {
    Cookies.set(PROJECT_COOKIE_NAME, project.id, { expires: 365 });
    set({ currentProject: project, isLoading: false, hydrated: true });
  },

  clearProject: () => {
    Cookies.remove(PROJECT_COOKIE_NAME);
    set({ currentProject: null, isLoading: false, hydrated: true });
  },

  setLoading: (isLoading) => set({ isLoading }),

  setHydrated: (hydrated) => set({ hydrated }),

  getProjectIdFromCookie: () => Cookies.get(PROJECT_COOKIE_NAME),
}));
