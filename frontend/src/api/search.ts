/**
 * api/search.ts — typed API client for search endpoints.
 */
import type { SearchResult, SearchMode } from '../types';

const BASE = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? '';

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) throw new Error(`Search API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const searchApi = {
  search: (query: string, mode: SearchMode = 'hybrid') =>
    req<SearchResult[]>(
      `/api/search?q=${encodeURIComponent(query)}&mode=${mode}`
    ),

  getSimilar: (noteId: string) =>
    req<SearchResult[]>(`/api/search/similar/${noteId}`),
};

export default searchApi;
