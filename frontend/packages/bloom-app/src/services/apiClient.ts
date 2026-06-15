import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * Axios instance pre-configured for session-cookie auth.
 *
 * - withCredentials: true → browser sends httpOnly cookies automatically
 * - On 401, redirects to /login (session expired or missing)
 */
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  withCredentials: true, // send session cookies with every request
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor — redirect to login on 401
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Avoid redirect loop if already on login page
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);
