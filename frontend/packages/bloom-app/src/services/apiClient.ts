import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// Mirrors kactus_common/user/const.py + csrf.py. The cookie is app-prefixed
// (not axios's default `XSRF-TOKEN`) so other *.labenry.com apps sharing
// `localhost` in dev — cookies ignore the port — cannot clobber it.
const CSRF_COOKIE_NAME = 'kactus_xsrf_token';
const CSRF_HEADER_NAME = 'X-XSRF-TOKEN';
export const CSRF_ERROR_CODE = 'CSRF_FAILED';

interface ApiErrorBody {
  code?: string;
}

interface RetriableConfig extends InternalAxiosRequestConfig {
  _csrfRetried?: boolean;
}

/**
 * Axios instance pre-configured for session-cookie auth.
 *
 * - withCredentials: true → browser sends httpOnly cookies automatically
 * - CSRF: axios echoes the `kactus_xsrf_token` cookie as `X-XSRF-TOKEN` on
 *   same-origin requests (never cross-origin — `withXSRFToken` stays unset).
 *   A 403 `CSRF_FAILED` (cookie missing/stale, e.g. a tab open across a
 *   deploy) refetches `/api/auth/me` — any session GET re-issues the cookie —
 *   and replays the request once.
 * - On 401, redirects to /login (session expired or missing)
 * - Array params repeat the key (`?code=SJC&code=999`) instead of axios's
 *   default `code[]=` form, which FastAPI does not parse into a list.
 */
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  withCredentials: true, // send session cookies with every request
  xsrfCookieName: CSRF_COOKIE_NAME,
  xsrfHeaderName: CSRF_HEADER_NAME,
  headers: {
    'Content-Type': 'application/json',
  },
  paramsSerializer: { indexes: null },
});

// Response interceptor — recover a stale CSRF cookie once; redirect to login on 401
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorBody>) => {
    const config = error.config as RetriableConfig | undefined;
    if (
      config &&
      !config._csrfRetried &&
      error.response?.status === 403 &&
      error.response.data?.code === CSRF_ERROR_CODE
    ) {
      config._csrfRetried = true;
      await apiClient.get('/api/auth/me');
      return apiClient(config);
    }
    if (error.response?.status === 401) {
      // Avoid redirect loop if already on login page
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);
