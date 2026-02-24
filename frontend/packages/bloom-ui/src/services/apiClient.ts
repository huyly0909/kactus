import axios from 'axios';
import { useAuthStore } from '../stores/authStore';

/**
 * Pre-configured Axios instance for kactus-fin API calls.
 * - Base URL from VITE_API_BASE_URL env var
 * - Auto-attaches JWT auth token from Zustand store
 * - Auto-refreshes expired tokens on 401
 */
export const apiClient = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:17600/api',
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Attach auth token to every request
apiClient.interceptors.request.use((config) => {
    const token = useAuthStore.getState().token;
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Handle 401 — attempt token refresh
apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;

            try {
                const refreshToken = useAuthStore.getState().refreshToken;
                if (!refreshToken) {
                    useAuthStore.getState().logout();
                    return Promise.reject(error);
                }

                const { data } = await axios.post(
                    `${apiClient.defaults.baseURL}/auth/refresh`,
                    { refreshToken },
                );

                useAuthStore.getState().setToken(data.data.accessToken);
                useAuthStore.getState().setRefreshToken(data.data.refreshToken);

                originalRequest.headers.Authorization = `Bearer ${data.data.accessToken}`;
                return apiClient(originalRequest);
            } catch {
                useAuthStore.getState().logout();
                return Promise.reject(error);
            }
        }

        return Promise.reject(error);
    },
);
