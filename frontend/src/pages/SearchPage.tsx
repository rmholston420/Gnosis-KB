/**
 * SearchPage
 * ==========
 * Full-text / semantic search across all notes.
 * Uses plain async/await with useEffect — no React Query dependency.
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Search, Loader2, FileText } from 'lucide-react';
import api from '../services/api';

interface SearchResult {
  id: string;
  title: string;
  slug: string;
  note_type: string;
  tags: string[];
  snippet?: string;
  score?: number;
}

interface SearchResponse {
  items: SearchResult[];
  total: number;
}

type SearchMode = 'fulltext' | 'semantic' | 'hybrid';

export default function SearchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQ = searchParams.get('q') ?? '';

  const [query, setQuery]       = useState(initialQ);
  const [mode, setMode]         = useState<SearchMode>('fulltext');
  const [results, setResults]   = useState<SearchResult[]>([]);
  const [total, setTotal]       = useState(0);
  const [isFetching, setFetching] = useState(false);
  const [isError, setError]     = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const doSearch = useCallback(async (q: string, m: SearchMode) => {
    if (!q.trim()) {
      setResults([]);
      setTotal(0);
      return;
    }
    setFetching(true);
    setError(false);
    try {
      const resp = await (api.searchNotes({ q, mode: m }) as Promise<SearchResponse>);
      setResults(resp.items ?? []);
      setTotal(resp.total ?? 0);
    } catch {
      setError(true);
    } finally {
      setFetching(false);
    }
  }, []);

  // Run search when query or mode changes (debounced)
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void doSearch(query, mode);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, mode, doSearch]);

  // Sync URL param
  useEffect(() => {
    if (query) {
      setSearchParams({ q: query }, { replace: true });
    } else {
      setSearchParams({}, { replace: true });
    }
  }, [query, setSearchParams]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="mb-6 text-xl font-semibold text-text-primary">Search</h1>

      {/* Search bar */}
      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-faint" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search notes…"
          autoFocus
          className="w-full rounded-xl border border-border-default bg-bg-secondary py-2.5 pl-9 pr-4 text-sm text-text-primary placeholder:text-text-faint focus:border-accent-teal focus:outline-none"
        />
        {isFetching && (
          <Loader2 size={14} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-text-faint" />
        )}
      </div>

      {/* Mode pills */}
      <div className="mb-6 flex gap-2">
        {(['fulltext', 'semantic', 'hybrid'] as SearchMode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`rounded-full px-3 py-1 text-xs transition-colors ${
              mode === m
                ? 'bg-accent-teal text-white'
                : 'text-text-muted hover:bg-bg-elevated'
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      {/* Error */}
      {isError && (
        <p className="text-sm text-error">Search failed — please try again.</p>
      )}

      {/* Results */}
      {!isFetching && !isError && query && results.length === 0 && (
        <p className="text-sm text-text-muted">No results found for &ldquo;{query}&rdquo;.</p>
      )}

      <div className="space-y-2">
        {results.map((r) => (
          <button
            key={r.id}
            onClick={() => navigate(`/notes/${r.id}`)}
            className="w-full rounded-xl border border-border-default bg-bg-secondary px-4 py-3 text-left transition-colors hover:bg-bg-elevated"
          >
            <div className="flex items-center gap-2">
              <FileText size={14} className="flex-shrink-0 text-text-faint" />
              <span className="text-sm font-medium text-text-primary">{r.title}</span>
            </div>
            {r.snippet && (
              <p className="mt-1 text-xs text-text-muted line-clamp-2">{r.snippet}</p>
            )}
          </button>
        ))}
      </div>

      {total > results.length && (
        <p className="mt-4 text-center text-xs text-text-muted">
          Showing {results.length} of {total} results
        </p>
      )}
    </div>
  );
}
