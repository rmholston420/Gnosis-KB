/**
 * useSearch — debounced search hooks for all search modes.
 */
import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { search, semanticSearch, findSimilar } from '../api/search';
import type { SearchParams, SearchMode } from '../api/search';
import type { SearchResponse, SearchResult } from '../types';

const DEBOUNCE_MS = 300;

/** Debounce a query string. Returns the debounced value. */
function useDebounce(value: string, ms = DEBOUNCE_MS): string {
  const [dv, setDv] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDv(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return dv;
}

/**
 * Generic debounced search hook.
 * `query` is the raw (non-debounced) search query.
 * Returns the TanStack Query result object directly.
 */
export function useSearch(query: string, mode: SearchMode = 'hybrid') {
  const dq = useDebounce(query);
  return useQuery<SearchResponse>({
    queryKey:  ['search', dq, mode],
    queryFn:   () => search({ q: dq, mode }),
    enabled:   dq.trim().length > 0,
    staleTime: 30_000,
  });
}

/** Hybrid search (BM25 + vector). */
export function useHybridSearch(query: string) {
  return useSearch(query, 'hybrid');
}

/** Keyword-only (BM25) search. */
export function useKeywordSearch(query: string) {
  return useSearch(query, 'keyword');
}

/** Semantic (vector-only) search. */
export function useSemanticSearch(q: string, limit = 10) {
  const dq = useDebounce(q);
  return useQuery<SearchResponse>({
    queryKey: ['search', 'semantic', dq, limit],
    queryFn:  () => semanticSearch(dq, limit),
    enabled:  dq.trim().length > 0,
    staleTime: 30_000,
  });
}

/** Find notes similar to a given note by embedding distance. */
export function useSimilarNotes(noteId: string | null, limit = 10) {
  return useQuery<SearchResult[]>({
    queryKey: ['search', 'similar', noteId, limit],
    queryFn:  () => findSimilar(noteId!, limit),
    enabled:  !!noteId,
    staleTime: 60_000,
  });
}
