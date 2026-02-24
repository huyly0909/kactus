import { apiClient } from './apiClient';
import type { ApiResponse, LoginRequest, LoginResponse } from '../types';

export const authService = {
    login: (credentials: LoginRequest) =>
        apiClient.post<ApiResponse<LoginResponse>>('/auth/login', credentials),

    logout: () => apiClient.post('/auth/logout'),

    me: () => apiClient.get<ApiResponse<LoginResponse['user']>>('/auth/me'),

    refresh: (refreshToken: string) =>
        apiClient.post<ApiResponse<{ accessToken: string; refreshToken: string }>>('/auth/refresh', {
            refreshToken,
        }),
};
