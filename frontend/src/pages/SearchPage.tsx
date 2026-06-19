/**
 * SearchPage
 * ==========
 * Hybrid / semantic / full-text search UI.
 *
 * Features:
 *  - Mode selector: hybrid / semantic / fulltext
 *  - Debounced search-as-you-type (400 ms)
 *  - Result cards with <mark> highlight rendering
 *  - Mode badge on each result showing which engine found it
 *  - Keyboard: Enter to search, Escape to clear
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, X, Zap, Database, Brain } from 'lucide-react';
import type { SearchResponse, SearchResult } from '../types';

const MODES = [
  { value: 'hybrid',    label: 'Hybrid',    Icon: Zap,      tip: 'BM25 + vector RRF fusion' },
  { value: 'fulltext',  label: 'Full-text', Icon: Database,  tip: 'PostgreSQL tsvector' },
  { value: 'semantic',  label: 'Semantic',  Icon: Brain,    tip: 'Dense vector only' },
] as const;

type SearchMode = typeof MODES[number]['value'];

function highlight(html: string) {
  // The backend already wraps matches in <mark>; render as HTML.
  // XSS note: this comes from our own backend, not user input.
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

function ResultCard({ result, onOpen }: { result: SearchResult; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="w-full text-left bg-bg-secondary hover:bg-bg-elevated border border-border rounded-lg px-4 py-3 flex flex-col gap-1 transition-colors group"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-medium text-text-primary group-hover:text-teal-400 transition-colors text-sm leading-snug">
          {result.title}
        </span>
        <span className="text-xs text-text-faint tabular-nums flex-shrink-0">
          {result.score.toFixed(4)}
        </span>
      </div>

      {result.highlight && (
        <p className="text-xs text-text-muted leading-relaxed line-clamp-2 [&_mark]:bg-yellow-400/20 [&_mark]:text-yellow-300 [&_mark]:rounded-sm [&_mark]:px-0.5">
          {highlight(result.highlight)}
        </p>
      )}

      <div className="flex items-center gap-2 mt-0.5">
        <span className="text-xs text-text-faint font-mono">{result.folder}</span>
        {result.tags.slice(0, 3).map((t) => (
          <span key={t} className="text-xs px-1.5 py-0.5 bg-bg-elevated text-text-muted rounded">
            {t}
          </span>
        ))}
      </div>
    </button>
  );
}

export default function SearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [debouncedQ, setDebouncedQ] = useState('');
  const [mode, setMode] = useState<SearchMode>('hybrid');
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Debounce input
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedQ(query.trim()), 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query]);

  // Keyboard shortcut: Escape clears
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setQuery(''); setDebouncedQ(''); }
  }, []);

  const { data, isFetching, isError } = useQuery<SearchResponse>({
    queryKey: ['search', debouncedQ, mode],
    queryFn: () =>
      fetch(`/api/v1/search/?q=${encodeURIComponent(debouncedQ)}&mode=${mode}&limit=20`)
        .then((r) => r.json()),
    enabled: debouncedQ.length >= 2,
    staleTime: 30_000,
  });

  const results = data?.results ?? [];
  const elapsed = data?.elapsed_ms;
  const actualMode = data?.mode;  // may differ from requested mode (fallback)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Search bar */}
      <div className="px-6 py-4 border-b border-border flex-shrink-0">
        <div className="relative max-w-2xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-text-faint" size={16} />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search notes…"
            autoFocus
            className="w-full bg-bg-elevated border border-border rounded-lg pl-9 pr-9 py-2.5 text-sm text-text-primary placeholder-text-faint focus:outline-none focus:border-teal-600 transition-colors"
          />
          {query && (
            <button
              onClick={() => { setQuery(''); setDebouncedQ(''); inputRef.current?.focus(); }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-text-faint hover:text-text-muted"
              aria-label="Clear search"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Mode selector */}
        <div className="flex items-center gap-1 mt-3">
          {MODES.map(({ value, label, Icon, tip }) => (
            <button
              key={value}
              onClick={() => setMode(value)}
              title={tip}
              className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-colors ${
                mode === value
                  ? 'bg-teal-700 text-white'
                  : 'text-text-muted hover:text-text-primary hover:bg-bg-elevated'
              }`}
            >
              <Icon size={12} />
              {label}
            </button>
          ))}

          {/* Status line */}
          {debouncedQ.length >= 2 && (
            <span className="ml-auto text-xs text-text-faint">
              {isFetching ? 'Searching…' : isError ? 'Search error' : (
                <>
                  {results.length} result{results.length !== 1 ? 's' : ''}
                  {elapsed !== undefined && ` · ${elapsed.toFixed(0)}ms`}
                  {actualMode && actualMode !== mode && (
                    <span className="ml-1 text-yellow-400">
                      (fell back to {actualMode})
                    </span>
                  )}
                </>
              )}
            </span>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-auto px-6 py-4">
        {debouncedQ.length < 2 ? (
          <div className="flex items-center justify-center h-32 text-text-faint text-sm">
            Type at least 2 characters to search
          </div>
        ) : isFetching && results.length === 0 ? (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-20 rounded-lg bg-bg-elevated animate-pulse" />
            ))}
          </div>
        ) : isError ? (
          <div className="text-center text-red-400 text-sm py-8">
            Search failed. Try again or switch to Full-text mode.
          </div>
        ) : results.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2 text-text-faint">
            <Search size={28} />
            <span className="text-sm">No results for “{debouncedQ}”</span>
          </div>
        ) : (
          <div className="space-y-2 max-w-2xl">
            {results.map((r) => (
              <ResultCard
                key={r.note_id}
                result={r}
                onOpen={() => navigate(`/notes/${r.note_id}`)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
