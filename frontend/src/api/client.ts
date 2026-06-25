/**
 * api/client.ts — low-level helpers used by the typed api/* modules.
 *
 * Exports two surfaces:
 *   1. fetch-based helpers (apiGet/apiPost/apiPut/apiDelete) — used by
 *      modules that don't need interceptors.
 *   2. axios-based `apiClient` — used by modules that need interceptors
 *      (auth token injection, 401 → logout redirect).
 */
import axios from 'axios';

// ── 1. Fetch-based helpers ──────────────────────────────────────────────────

const BASE =
  (typeof import.meta !== 'undefined'
    ? (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE_URL
    : undefined) ?? '/api';

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token =
    typeof localStorage !== 'undefined' ? localStorage.getItem('gnosis_token') : null;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${method} ${path} → ${res.status}: ${text}`);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

export const apiGet    = <T>(path: string)                 => request<T>('GET',    path);
export const apiPost   = <T>(path: string, body?: unknown) => request<T>('POST',   path, body);
export const apiPut    = <T>(path: string, body?: unknown) => request<T>('PUT',    path, body);
export const apiDelete = <T = void>(path: string)          => request<T>('DELETE', path);

// ── 2. Axios client with interceptors ─────────────────────────────────────

export const apiClient = axios.create({
  baseURL: BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor — inject Bearer token from localStorage
apiClient.interceptors.request.use((config) => {
  const token =
    typeof localStorage !== 'undefined' ? localStorage.getItem('gnosis_token') : null;
  if (token && config.headers) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — on 401, clear token and redirect to /login
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('gnosis_token');
      }
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

// Default export for modules that do: import client from './client'
export default apiClient;
