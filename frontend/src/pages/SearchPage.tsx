/**
 * SearchPage — full-text, semantic and hybrid search UI.
 */
import React, { useState, useCallback } from 'react';
import { useSearch } from '../hooks/useSearch';
import type { SearchMode } from '../hooks/useSearch';
import type { SearchResult } from '../types';

// 'keyword' maps to 'fulltext' in the API — use SearchMode-safe values
const MODES: { label: string; value: SearchMode }[] = [
  { label: 'Hybrid',   value: 'hybrid'   },
  { label: 'Semantic', value: 'semantic' },
  { label: 'Fulltext', value: 'fulltext' },
];

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [mode,  setMode]  = useState<SearchMode>('hybrid');

  const { data, isLoading, isError } = useSearch(query, mode);
  const results: SearchResult[] = data?.items ?? [];

  const handleInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
  }, []);

  return (
    <div className="flex flex-col h-full bg-gnosis-bg text-gnosis-fg">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-gnosis-border">
        <h1 className="text-xl font-semibold mb-3">Search</h1>

        {/* Search input */}
        <input
          type="search"
          value={query}
          onChange={handleInput}
          placeholder="Search your vault\u2026"
          className="w-full rounded-lg bg-gnosis-surface border border-gnosis-border px-4 py-2 text-sm
                     focus:outline-none focus:border-gnosis-accent placeholder:text-gnosis-muted"
          autoFocus
        />

        {/* Mode tabs */}
        <div className="flex gap-2 mt-3">
          {MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => setMode(m.value)}
              className={[
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                mode === m.value
                  ? 'bg-gnosis-accent text-white'
                  : 'bg-gnosis-surface text-gnosis-muted hover:text-gnosis-fg',
              ].join(' ')}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {isLoading && (
          <p className="text-sm text-gnosis-muted animate-pulse">Searching\u2026</p>
        )}
        {isError && (
          <p className="text-sm text-red-500">Search failed. Please try again.</p>
        )}
        {!isLoading && results.length === 0 && query.trim().length > 0 && (
          <p className="text-sm text-gnosis-muted">No results for \u201c{query}\u201d.</p>
        )}
        <ul className="space-y-3">
          {results.map((r) => (
            <li
              key={r.note_id}
              className="rounded-lg border border-gnosis-border bg-gnosis-surface p-4 hover:border-gnosis-accent transition-colors cursor-pointer"
            >
              <p className="text-sm font-medium text-gnosis-fg">{r.title}</p>
              {(r.excerpt ?? r.snippet) && (
                <p className="mt-1 text-xs text-gnosis-muted line-clamp-2">
                  {r.excerpt ?? r.snippet}
                </p>
              )}
              <div className="mt-2 flex flex-wrap gap-1">
                {r.tags?.map((t) => (
                  <span key={t} className="rounded-full bg-gnosis-accent/10 px-2 py-0.5 text-xs text-gnosis-accent">
                    #{t}
                  </span>
                ))}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
