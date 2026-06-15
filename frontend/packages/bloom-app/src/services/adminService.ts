import { apiClient } from './apiClient';
import type { ApiResponse } from '../types';
import type { Project } from '../types/project';

interface Pagination<T> {
  total: number;
  items: T[];
}

interface UserInfo {
  id: string;
  email: string;
  name: string;
  status: string;
  is_superuser: boolean;
}

interface CreateUserPayload {
  email: string;
  name: string;
  password: string;
  is_superuser?: boolean;
}

interface UpdateUserRolePayload {
  is_superuser: boolean;
}

interface ResetPasswordResponse {
  new_password: string;
}

interface PermissionItem {
  permission: string;
  act: string;
}

type AuthorizationResponse = Record<string, PermissionItem[]>;

/**
 * Admin service — superuser-only management operations.
 */
export const adminService = {
  /** List all users (admin only). */
  getUsers: async () => {
    const { data } = await apiClient.get<ApiResponse<Pagination<UserInfo>>>('/api/admin/users');
    return data.data;
  },

  /** Create a new user (admin only). */
  createUser: async (payload: CreateUserPayload) => {
    const { data } = await apiClient.post<ApiResponse<UserInfo>>('/api/admin/users', payload);
    return data.data;
  },

  /** Update a user's superuser role (admin only). */
  updateUserRole: async (userId: string, payload: UpdateUserRolePayload) => {
    const { data } = await apiClient.put<ApiResponse<UserInfo>>(
      `/api/admin/users/${userId}/role`,
      payload,
    );
    return data.data;
  },

  /** Reset a user's password (admin only). Returns the new random password. */
  resetPassword: async (userId: string) => {
    const { data } = await apiClient.post<ApiResponse<ResetPasswordResponse>>(
      `/api/admin/users/${userId}/reset-password`,
    );
    return data.data;
  },

  /** Deactivate a user (admin only). */
  deactivateUser: async (userId: string) => {
    const { data } = await apiClient.post<ApiResponse<UserInfo>>(
      `/api/admin/users/${userId}/deactivate`,
    );
    return data.data;
  },

  /** List all projects (admin only). */
  getAllProjects: async () => {
    const { data } = await apiClient.get<ApiResponse<Pagination<Project>>>('/api/admin/projects');
    return data.data;
  },

  /** Get role-permission authorization mappings. */
  getAuthorization: async () => {
    const { data } = await apiClient.get<ApiResponse<AuthorizationResponse>>(
      '/api/admin/authorization',
    );
    return data.data;
  },
};
