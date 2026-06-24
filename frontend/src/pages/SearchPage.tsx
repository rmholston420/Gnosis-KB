import React, { useState, useCallback } from 'react';
import { useSearch } from '../hooks/useSearch';
import SearchResults from '../components/search/SearchResults';
import SemanticSearch from '../components/search/SemanticSearch';
import type { SearchMode } from '../types';

const MODES: { label: string; value: SearchMode }[] = [
  { label: 'Hybrid',   value: 'hybrid'   },
  { label: 'Semantic', value: 'semantic' },
  { label: 'Keyword',  value: 'keyword'  },
  { label: 'Full-text',value: 'fulltext' },
];

export default function SearchPage() {
  const [query,  setQuery]  = useState('');
  const [mode,   setMode]   = useState<SearchMode>('hybrid');
  const [input,  setInput]  = useState('');

  // Debounced search via hook
  const { data, isLoading, isError } = useSearch(query, mode);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      setQuery(input.trim());
    },
    [input],
  );

  return (
    <div className="flex flex-col h-full bg-gnosis-bg text-gnosis-fg">
      {/* ── Header ── */}
      <div className="px-6 pt-6 pb-4 border-b border-gnosis-border">
        <h1 className="text-xl font-semibold mb-4">Search</h1>

        {/* Mode tabs */}
        <div className="flex gap-1 mb-4" role="tablist">
          {MODES.map((m) => (
            <button
              key={m.value}
              role="tab"
              aria-selected={mode === m.value}
              onClick={() => setMode(m.value)}
              className={[
                'px-3 py-1.5 rounded text-sm transition-colors',
                mode === m.value
                  ? 'bg-gnosis-surface text-gnosis-fg font-medium shadow-sm'
                  : 'text-gnosis-muted hover:text-gnosis-fg hover:bg-gnosis-surface',
              ].join(' ')}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Search bar — only for non-semantic modes */}
        {mode !== 'semantic' && (
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="search"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Search your vault…"
              className="flex-1 px-3 py-2 rounded bg-gnosis-surface border border-gnosis-border text-gnosis-fg placeholder-gnosis-muted text-sm focus:outline-none focus:ring-2 focus:ring-gnosis-accent"
            />
            <button
              type="submit"
              className="px-4 py-2 rounded bg-gnosis-accent text-white text-sm font-medium hover:opacity-90 transition-opacity"
            >
              Search
            </button>
          </form>
        )}
      </div>

      {/* ── Body ── */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {mode === 'semantic' ? (
          <SemanticSearch />
        ) : (
          <SearchResults
            results={data?.items ?? data?.results ?? []}
            query={query}
            isLoading={isLoading}
            isError={isError}
          />
        )}
      </div>
    </div>
  );
}
