import { apiClient } from './apiClient';
import type { ApiResponse } from '@/types';
import type { Project } from '@/types/project';
import type {
  AdminUser,
  AuthorizationMap,
  CreateUserPayload,
  ResetPasswordResponse,
  UpdateUserRolePayload,
} from '@/types/admin';

/** Backend `Pagination[T]` envelope — `{ total, items }`. */
export interface Pagination<T> {
  total: number;
  items: T[];
}

/**
 * Admin service — superuser-only management operations.
 */
export const adminService = {
  /** List all users (admin only). */
  getUsers: async () => {
    const { data } = await apiClient.get<ApiResponse<Pagination<AdminUser>>>('/api/admin/users');
    return data.data;
  },

  /** Create a new user (admin only). */
  createUser: async (payload: CreateUserPayload) => {
    const { data } = await apiClient.post<ApiResponse<AdminUser>>('/api/admin/users', payload);
    return data.data;
  },

  /** Update a user's superuser role (admin only). */
  updateUserRole: async (userId: string, payload: UpdateUserRolePayload) => {
    const { data } = await apiClient.put<ApiResponse<AdminUser>>(
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
    const { data } = await apiClient.post<ApiResponse<AdminUser>>(
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
    const { data } = await apiClient.get<ApiResponse<AuthorizationMap>>('/api/admin/authorization');
    return data.data;
  },
};
