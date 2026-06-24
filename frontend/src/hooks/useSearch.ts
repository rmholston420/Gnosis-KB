/**
 * useSearch hook — TanStack Query wrapper for the search endpoints.
 */
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { SearchResult } from '../types';

export type SearchMode = 'hybrid' | 'semantic' | 'fulltext' | 'keyword';

export interface UseSearchParams {
  q:       string;
  mode?:   SearchMode;
  limit?:  number;
  offset?: number;
  tags?:   string[];
}

export function useSearch(params: UseSearchParams) {
  return useQuery<SearchResult[]>({
    queryKey: ['search', params],
    queryFn:  () => api.search(params.q, params.mode ?? 'hybrid', params.limit) as Promise<SearchResult[]>,
    enabled:  params.q.trim().length > 0,
    staleTime: 30_000,
  });
}

export default useSearch;
