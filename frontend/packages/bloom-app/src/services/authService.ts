import { apiClient } from './apiClient';
import type { ApiResponse } from '../types';

export interface UserInfo {
  id: string;
  email: string;
  username: string;
  name: string;
  status: string;
  is_superuser: boolean;
  language?: string | null;
  timezone?: string | null;
}

interface LoginResponse {
  user: UserInfo;
}

interface LoginPayload {
  email: string;
  password: string;
  remember?: boolean;
}

export interface PreferencesPayload {
  language?: string;
  timezone?: string;
}

/**
 * Auth service — session-based, cookies sent automatically via withCredentials.
 */
export const authService = {
  /** Login with email + password. Cookie is set by the server. */
  login: async (payload: LoginPayload) => {
    const { data } = await apiClient.post<ApiResponse<LoginResponse>>('/api/auth/login', payload);
    return data.data;
  },

  /** Logout — server clears the session cookie. */
  logout: async () => {
    await apiClient.post('/api/auth/logout');
  },

  /** Get current user from session cookie. */
  me: async () => {
    const { data } = await apiClient.get<ApiResponse<UserInfo>>('/api/auth/me');
    return data.data;
  },

  /** Update the current user's own UI preferences (language, timezone). */
  updatePreferences: async (payload: PreferencesPayload) => {
    const { data } = await apiClient.patch<ApiResponse<UserInfo>>('/api/auth/me', payload);
    return data.data;
  },
};
