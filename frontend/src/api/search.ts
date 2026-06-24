/**
 * api/search.ts — typed wrappers for the search endpoints.
 */
import { apiGet } from './client';
import type { SearchResult } from '../types';

export type SearchMode = 'hybrid' | 'semantic' | 'fulltext' | 'keyword';

export interface SearchParams {
  q:       string;
  mode?:   SearchMode;
  limit?:  number;
  offset?: number;
  tags?:   string[];
}

export interface SearchResponse {
  results: SearchResult[];
  total:   number;
  took_ms: number;
}

export async function searchNotes(params: SearchParams): Promise<SearchResponse> {
  const qs = new URLSearchParams();
  qs.set('q', params.q);
  if (params.mode)   qs.set('mode',   params.mode);
  if (params.limit)  qs.set('limit',  String(params.limit));
  if (params.offset) qs.set('offset', String(params.offset));
  if (params.tags?.length) qs.set('tags', params.tags.join(','));
  return apiGet<SearchResponse>(`/search?${qs.toString()}`);
}

export async function semanticSearch(q: string, limit = 10): Promise<SearchResponse> {
  return searchNotes({ q, mode: 'semantic', limit });
}

export async function keywordSearch(q: string, limit = 20): Promise<SearchResponse> {
  return searchNotes({ q, mode: 'keyword', limit });
}
