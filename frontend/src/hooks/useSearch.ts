/**
 * useSearch — debounced hybrid search hook.
 */
import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { search, semanticSearch, findSimilar } from '../api/search';
import type { SearchParams, SearchMode } from '../api/search';
import type { SearchResponse, SearchResult } from '../types';

const DEBOUNCE_MS = 300;

/**
 * Debounced hybrid search. Returns results, loading state, and error.
 * Automatically refires when query or mode changes after the debounce window.
 */
export function useSearch(initialQuery = '', initialMode: SearchMode = 'hybrid') {
  const [query, setQuery]   = useState(initialQuery);
  const [mode,  setMode]    = useState<SearchMode>(initialMode);
  const [debouncedQ, setDQ] = useState(initialQuery);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setDQ(query), DEBOUNCE_MS);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [query]);

  const { data, isLoading, isError, error } = useQuery<SearchResponse>({
    queryKey:  ['search', debouncedQ, mode],
    queryFn:   () => search({ q: debouncedQ, mode }),
    enabled:   debouncedQ.trim().length > 0,
    staleTime: 30_000,
  });

  return {
    query, setQuery,
    mode,  setMode,
    results:   data?.items ?? [],
    total:     data?.total ?? 0,
    isLoading,
    isError,
    error,
  };
}

/** Semantic-only search hook. */
export function useSemanticSearch(q: string, limit = 10) {
  return useQuery<SearchResponse>({
    queryKey: ['search', 'semantic', q, limit],
    queryFn:  () => semanticSearch(q, limit),
    enabled:  q.trim().length > 0,
    staleTime: 30_000,
  });
}

/** Find similar notes to a given note ID. */
export function useSimilarNotes(noteId: string | null, limit = 10) {
  return useQuery<SearchResult[]>({
    queryKey: ['search', 'similar', noteId, limit],
    queryFn:  () => findSimilar(noteId!, limit),
    enabled:  !!noteId,
    staleTime: 60_000,
  });
}
