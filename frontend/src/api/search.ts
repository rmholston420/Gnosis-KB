/**
 * Search API — typed wrappers around /api/v1/search endpoints.
 *
 * FIX: removed /api/v1 prefix from all paths. api/client.ts already sets
 * baseURL to /api/v1, so each path here is the suffix only. Previously every
 * request resolved to /api/v1/api/v1/search, returning 404.
 */
import client from './client';
import type { SearchResult, SearchResponse } from '../types';

export type SearchMode = 'hybrid' | 'semantic' | 'fulltext';

export interface SearchParams {
  q: string;
  mode?: SearchMode;
  limit?: number;
  offset?: number;
  folder?: string;
  tags?: string;
  page?: number;
}

/** Hybrid BM25 + vector RRF fusion search (default). */
export async function search(params: SearchParams): Promise<SearchResponse> {
  const { data } = await client.get<SearchResponse>('/search', { params });
  return data;
}

/** Pure semantic (dense vector) search. */
export async function semanticSearch(q: string, limit = 10): Promise<SearchResponse> {
  const { data } = await client.get<SearchResponse>('/search/semantic', {
    params: { q, limit },
  });
  return data;
}

/** Pure BM25 full-text search. */
export async function fulltextSearch(q: string, limit = 10): Promise<SearchResponse> {
  const { data } = await client.get<SearchResponse>('/search/fulltext', {
    params: { q, limit },
  });
  return data;
}

/** Search by tags. */
export async function searchByTags(tags: string[], limit = 20): Promise<SearchResponse> {
  const { data } = await client.get<SearchResponse>('/search/tags', {
    params: { tags: tags.join(','), limit },
  });
  return data;
}

/** Find semantically similar notes to a given note. */
export async function findSimilar(
  noteId: string,
  limit = 5,
): Promise<SearchResult[]> {
  const { data } = await client.get<SearchResult[]>(`/search/similar/${noteId}`, {
    params: { limit },
  });
  return data;
}
