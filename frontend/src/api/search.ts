import type { SearchResult, SearchMode } from '../types';

const BASE = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? '';

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const url = BASE ? `${BASE}${path}` : new URL(path, 'http://localhost').toString();
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) throw new Error(`Search API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export async function searchNotes(query: string, mode: SearchMode = 'hybrid') {
  return req<{ query: string; mode: SearchMode; items: SearchResult[]; total: number }>(
    `/api/search?q=${encodeURIComponent(query)}&mode=${mode}`,
  );
}

export async function getSimilarNotes(noteId: string) {
  return req<SearchResult[]>(`/api/search/similar/${noteId}`);
}

export const searchApi = {
  search: async (query: string, mode: SearchMode = 'hybrid') => {
    const res = await searchNotes(query, mode);
    return res.items;
  },
  getSimilar: getSimilarNotes,
};

export default searchApi;
