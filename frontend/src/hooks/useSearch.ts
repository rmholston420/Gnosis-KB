/**
 * hooks/useSearch.ts — TanStack Query hooks for search.
 * Exports named hooks for each search mode so tests can spy on them.
 */
import { useQuery } from '@tanstack/react-query';
import { searchApi } from '../api/search';
import type { SearchResult, SearchMode } from '../types';

const SEARCH_KEY = 'search';

// ── Generic / default hook ────────────────────────────────────────────────────

export function useSearch(query: string, mode: SearchMode = 'hybrid') {
  return useQuery({
    queryKey: [SEARCH_KEY, mode, query],
    queryFn:  () => searchApi.search(query, mode),
    enabled:  query.trim().length > 0,
  });
}

export default useSearch;

// ── Named per-mode hooks (used by SearchPage, SemanticSearch, tests) ──────────

export function useHybridSearch(query: string) {
  return useSearch(query, 'hybrid');
}

export function useKeywordSearch(query: string) {
  return useSearch(query, 'keyword');
}

export function useSemanticSearch(query: string) {
  return useSearch(query, 'semantic');
}

// ── Similar notes ─────────────────────────────────────────────────────────────

export function useSimilarNotes(noteId: string | null | undefined) {
  return useQuery({
    queryKey: [SEARCH_KEY, 'similar', noteId],
    queryFn:  () => searchApi.getSimilar(noteId!),
    enabled:  Boolean(noteId),
    select:   (d: SearchResult[]) => d,
  });
}
