import { apiClient } from './apiClient';
import type { ApiResponse } from '../types';
import type { Project, ProjectMemberDetail, PermissionsResponse } from '../types/project';

export interface Pagination<T> {
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

export interface AddMemberPayload {
  email: string;
  role: string;
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

  // ------------------------------------------------------------- members

  /** List a project's members (with email/name for display). */
  getMembers: async (projectId: string) => {
    const { data } = await apiClient.get<ApiResponse<Pagination<ProjectMemberDetail>>>(
      `/api/projects/${projectId}/members`,
    );
    return data.data;
  },

  /** Invite an existing user by exact email + role. No directory search by design. */
  addMember: async (projectId: string, payload: AddMemberPayload) => {
    const { data } = await apiClient.post<ApiResponse<ProjectMemberDetail>>(
      `/api/projects/${projectId}/members`,
      payload,
    );
    return data.data;
  },

  /** Change a member's role. */
  updateMemberRole: async (projectId: string, userId: string, role: string) => {
    const { data } = await apiClient.patch<ApiResponse<ProjectMemberDetail>>(
      `/api/projects/${projectId}/members/${userId}`,
      { role },
    );
    return data.data;
  },

  /** Remove a member from the project. */
  removeMember: async (projectId: string, userId: string) => {
    await apiClient.delete(`/api/projects/${projectId}/members/${userId}`);
  },
};
