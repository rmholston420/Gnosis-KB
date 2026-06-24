/**
 * Search API — typed wrappers around /api/v1/search endpoints.
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
}

/** Hybrid BM25 + vector RRF fusion search (default). */
export async function search(params: SearchParams): Promise<SearchResponse> {
  const { data } = await client.get<SearchResponse>('/api/v1/search', { params });
  return data;
}

/** Pure semantic (dense vector) search. */
export async function semanticSearch(q: string, limit = 10): Promise<SearchResponse> {
  const { data } = await client.get<SearchResponse>('/api/v1/search/semantic', {
    params: { q, limit },
  });
  return data;
}

/** Pure BM25 full-text search. */
export async function fulltextSearch(q: string, limit = 10): Promise<SearchResponse> {
  const { data } = await client.get<SearchResponse>('/api/v1/search/fulltext', {
    params: { q, limit },
  });
  return data;
}

/** Search by tags. */
export async function searchByTags(tags: string[], limit = 20): Promise<SearchResponse> {
  const { data } = await client.get<SearchResponse>('/api/v1/search/tags', {
    params: { tags: tags.join(','), limit },
  });
  return data;
}

/** Find semantically similar notes to a given note. */
export async function findSimilar(
  noteId: string,
  limit = 5,
): Promise<SearchResult[]> {
  const { data } = await client.get<SearchResult[]>(`/api/v1/search/similar/${noteId}`, {
    params: { limit },
  });
  return data;
}
