/**
 * SearchPage — full-text / semantic / hybrid search UI.
 *
 * SearchMode is imported from hooks/useSearch (which re-exports it
 * from api/search) so there is a single source of truth.
 */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useSearch, SearchMode } from '../hooks/useSearch';
import type { SearchResult } from '../types';

const MODES: { label: string; value: SearchMode }[] = [
  { label: 'Hybrid',   value: 'hybrid'   },
  { label: 'Semantic', value: 'semantic' },
  { label: 'Keyword',  value: 'keyword'  },
];

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [mode,  setMode]  = useState<SearchMode>('hybrid');

  const { data, isLoading, isError } = useSearch(query, mode);
  const results = (data?.items ?? []) as SearchResult[];
  const total   = data?.total ?? 0;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-lg font-semibold text-gnosis-fg mb-4">Search</h1>

      {/* Search form */}
      <form onSubmit={handleSubmit} className="flex gap-2 mb-4">
        <input
          role="searchbox"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search notes…"
          className="flex-1 px-3 py-2 rounded-md bg-gnosis-bg border border-gnosis-border
                     text-gnosis-fg text-sm focus:outline-none focus:ring-2 focus:ring-gnosis-accent"
        />
        <button
          type="submit"
          className="px-4 py-2 rounded-md bg-gnosis-accent text-white text-sm font-medium
                     hover:opacity-90 transition-opacity"
        >
          Search
        </button>
      </form>

      {/* Mode tabs */}
      <div role="tablist" className="flex gap-1 mb-6">
        {MODES.map((m) => (
          <button
            key={m.value}
            role="tab"
            aria-selected={mode === m.value}
            onClick={() => setMode(m.value)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors
              ${
                mode === m.value
                  ? 'bg-gnosis-accent text-white'
                  : 'bg-gnosis-surface text-gnosis-muted hover:text-gnosis-fg'
              }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* States */}
      {isLoading && (
        <p className="text-sm text-gnosis-muted animate-pulse">Searching…</p>
      )}

      {isError && (
        <p role="alert" className="text-sm text-red-500">Search failed. Please try again.</p>
      )}

      {!isLoading && !isError && query && results.length === 0 && (
        <p className="text-sm text-gnosis-muted">No results for “{query}”.</p>
      )}

      {/* Result count */}
      {results.length > 0 && (
        <p className="text-xs text-gnosis-muted mb-3">{total} results</p>
      )}

      {/* Result list */}
      <ul className="space-y-3">
        {results.map((r) => (
          <li key={r.note_id}>
            <Link
              to={`/notes/${r.note_id}`}
              className="block p-4 rounded-lg bg-gnosis-surface border border-gnosis-border
                         hover:border-gnosis-accent transition-colors"
            >
              <h2 className="text-sm font-semibold text-gnosis-fg">{r.title}</h2>
              {(r.snippet ?? r.excerpt) && (
                <p className="mt-1 text-xs text-gnosis-muted line-clamp-2">
                  {r.snippet ?? r.excerpt}
                </p>
              )}
              {r.tags && r.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {r.tags.map((tag: string) => (
                    <span
                      key={tag}
                      className="px-1.5 py-0.5 rounded-full bg-gnosis-accent/10 text-gnosis-accent text-xs"
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
