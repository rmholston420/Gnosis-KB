/**
 * api/client.ts
 * Centralised Axios instance for all Gnosis API calls.
 * Base URL comes from the VITE_API_BASE_URL env var (default: same origin).
 */
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

// Attach JWT from localStorage on every request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('gnosis_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Redirect to /login on 401
apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('gnosis_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  },
);

// Default export so `import client from './client'` works in api/* modules
// AND named export is preserved for direct imports.
export default apiClient;
