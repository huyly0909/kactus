import { apiClient } from './apiClient';
import type { ApiResponse } from '../types';
import type { Project, PermissionsResponse } from '../types/project';

interface Pagination<T> {
  total: number;
  items: T[];
}

interface ProjectCreatePayload {
  name: string;
  code: string;
  description?: string;
}

interface ProjectUpdatePayload {
  name?: string;
  code?: string;
  description?: string;
}

/**
 * Project service — CRUD operations and permission queries.
 */
export const projectService = {
  /** List projects for the current user. */
  getProjects: async () => {
    const { data } = await apiClient.get<ApiResponse<Pagination<Project>>>('/api/projects');
    return data.data;
  },

  /** Get a single project by ID. */
  getProjectById: async (projectId: string) => {
    const { data } = await apiClient.get<ApiResponse<Project>>(`/api/projects/${projectId}`);
    return data.data;
  },

  /** Create a new project. */
  createProject: async (payload: ProjectCreatePayload) => {
    const { data } = await apiClient.post<ApiResponse<Project>>('/api/projects', payload);
    return data.data;
  },

  /** Update a project. */
  updateProject: async (projectId: string, payload: ProjectUpdatePayload) => {
    const { data } = await apiClient.put<ApiResponse<Project>>(
      `/api/projects/${projectId}`,
      payload,
    );
    return data.data;
  },

  /** Delete a project (logical). */
  deleteProject: async (projectId: string) => {
    await apiClient.delete(`/api/projects/${projectId}`);
  },

  /** Get current user's permissions for a project. */
  getMyPermissions: async (projectId: string) => {
    const { data } = await apiClient.get<ApiResponse<PermissionsResponse>>('/api/me/permissions', {
      params: { project_id: projectId },
    });
    return data.data;
  },
};
