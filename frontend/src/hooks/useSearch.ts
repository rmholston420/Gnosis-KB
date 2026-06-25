/**
 * useSearch — TanStack Query hook for full-text / semantic / hybrid search.
 *
 * Imports from api/search. Re-exports SearchMode so pages can import
 * it from this module instead of reaching into api/search directly.
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { SearchMode } from '../api/search';
import { search as searchNotes, findSimilar } from '../api/search';
import type { SearchParams } from '../api/search';

// Re-export SearchMode so SearchPage.tsx, useAI.ts, etc. can import from here
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
  return useSearch(query, 'fulltext');
}

export function useSemanticSearch(query: string) {
  return useSearch(query, 'semantic');
}

export function useHybridSearch(query: string) {
  return useSearch(query, 'hybrid');
}

/** Find notes semantically similar to a given note ID. */
export function useSimilarNotes(noteId: string | null | undefined, limit = 5) {
  return useQuery({
    queryKey: ['search', 'similar', noteId, limit],
    queryFn:  () => findSimilar(noteId!, limit),
    enabled:  !!noteId,
    staleTime: 60_000,
  });
}
