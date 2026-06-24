/**
 * hooks/useSearch.ts — TanStack Query hooks for search.
 * All named exports so tests can spy on individual hooks.
 */
import { useQuery } from '@tanstack/react-query';
import { searchApi } from '../api/search';
import type { SearchResponse, SearchResult, SearchMode } from '../types';

// Re-export SearchMode so pages can import it from here
export type { SearchMode };

const SEARCH_KEY = 'search';

// ── Generic hook ──────────────────────────────────────────────────────────────

export function useSearch(query: string, mode: SearchMode = 'hybrid') {
  return useQuery({
    queryKey: [SEARCH_KEY, mode, query],
    queryFn:  async (): Promise<SearchResponse> => {
      const items = await searchApi.search(query, mode);
      return { items, total: items.length };
    },
    enabled: query.trim().length > 0,
  });
}

export default useSearch;

// ── Named per-mode hooks ──────────────────────────────────────────────────────

export function useHybridSearch(query: string)  { return useSearch(query, 'hybrid');   }
export function useKeywordSearch(query: string) { return useSearch(query, 'keyword');  }
export function useSemanticSearch(query: string){ return useSearch(query, 'semantic'); }

// ── Similar notes ─────────────────────────────────────────────────────────────

export function useSimilarNotes(noteId: string | null | undefined) {
  return useQuery({
    queryKey: [SEARCH_KEY, 'similar', noteId],
    queryFn:  (): Promise<SearchResult[]> => searchApi.getSimilar(noteId!),
    enabled:  Boolean(noteId),
  });
}
