/**
 * useSearch — TanStack Query hook for full-text / semantic / hybrid search.
 *
 * Re-exports SearchMode from types so pages can import it from one place.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { SearchParams, SearchMode } from '../api/search';
import { searchNotes } from '../api/search';

// Re-export SearchMode so SearchPage.tsx can import it from this module
export type { SearchMode };

export function useSearch(query: string, mode: SearchMode = 'hybrid') {
  const [page, setPage] = useState(1);

  const result = useQuery({
    queryKey: ['search', query, mode, page],
    queryFn:  () => searchNotes({ q: query, mode, page } as SearchParams),
    enabled:  query.trim().length > 0,
    staleTime: 30_000,
  });

  return { ...result, page, setPage };
}

export function useKeywordSearch(query: string) {
  return useSearch(query, 'keyword');
}

export function useSemanticSearch(query: string) {
  return useSearch(query, 'semantic');
}

export function useHybridSearch(query: string) {
  return useSearch(query, 'hybrid');
}
