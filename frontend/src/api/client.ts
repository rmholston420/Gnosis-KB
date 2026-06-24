/**
 * api/client.ts — low-level fetch helpers used by the typed api/* modules.
 * Reads the VITE_API_BASE_URL env var (defaults to /api).
 */

const BASE = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE_URL) ?? '/api';

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

export const apiGet    = <T>(path: string)                => request<T>('GET',    path);
export const apiPost   = <T>(path: string, body?: unknown) => request<T>('POST',   path, body);
export const apiPut    = <T>(path: string, body?: unknown) => request<T>('PUT',    path, body);
export const apiDelete = <T = void>(path: string)         => request<T>('DELETE', path);
