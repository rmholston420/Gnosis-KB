/**
 * hooks/useSearch.ts — TanStack Query hooks for search.
 */
import { useQuery } from '@tanstack/react-query';
import { searchNotes, getSimilarNotes } from '../api/search';
import type { SearchResponse, SearchResult, SearchMode } from '../types';

export type { SearchMode };

const SEARCH_KEY = 'search';

export function useSearch(query: string, mode: SearchMode = 'hybrid') {
  return useQuery({
    queryKey: [SEARCH_KEY, mode, query],
    queryFn: () => searchNotes(query, mode) as Promise<SearchResponse>,
    enabled: query.trim().length > 0,
  });
}

export default useSearch;

export function useHybridSearch(query: string) { return useSearch(query, 'hybrid'); }
export function useKeywordSearch(query: string) { return useSearch(query, 'keyword'); }
export function useSemanticSearch(query: string) { return useSearch(query, 'semantic'); }

export function useSimilarNotes(noteId: string | null | undefined) {
  return useQuery({
    queryKey: [SEARCH_KEY, 'similar', noteId],
    queryFn: () => getSimilarNotes(noteId!) as Promise<SearchResult[]>,
    enabled: Boolean(noteId),
  });
}
