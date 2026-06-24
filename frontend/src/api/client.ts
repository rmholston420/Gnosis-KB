/**
 * Gnosis-KB API client
 * -  Attaches Bearer token from localStorage on every request.
 * -  On 401: clears token + redirects to /login.
 * -  On all other 4xx/5xx: rejects with the AxiosError so callers can handle.
 */
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env?.VITE_API_BASE_URL ?? '',
  headers: { 'Content-Type': 'application/json' },
});

// ── Request interceptor: attach token ─────────────────────────────────────────
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('gnosis_token');
    if (token) {
      config.headers = config.headers ?? {};
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ── Response interceptor: handle 401, pass through everything else ────────────
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem('gnosis_token');
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export default apiClient;
