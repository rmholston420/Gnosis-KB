/**
 * SearchPage — hybrid + semantic search UI.
 */
import React, { useState } from 'react';
import { SearchResults } from '../components/search/SearchResults';
import { SemanticSearch } from '../components/search/SemanticSearch';
import type { SearchMode } from '../hooks/useSearch';

export default function SearchPage() {
  const [query, setQuery]   = useState('');
  const [mode, setMode]     = useState<SearchMode>('hybrid');
  const [submitted, setSubmitted] = useState('');

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(query);
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gnosis-fg mb-6">Search</h1>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="flex gap-2 mb-4">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search your vault…"
          className="flex-1 rounded-lg border border-gnosis-border bg-gnosis-surface px-3 py-2 text-sm text-gnosis-fg placeholder:text-gnosis-muted focus:outline-none focus:ring-2 focus:ring-gnosis-accent"
        />
        <button
          type="submit"
          className="px-4 py-2 rounded-lg bg-gnosis-accent text-white text-sm font-medium hover:opacity-90 transition-opacity"
        >
          Search
        </button>
      </form>

      {/* Mode tabs */}
      <div className="flex gap-1 mb-6">
        {(['hybrid', 'semantic', 'fulltext'] as SearchMode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={[
              'px-3 py-1 rounded-md text-xs font-medium transition-colors',
              mode === m
                ? 'bg-gnosis-accent text-white'
                : 'bg-gnosis-surface text-gnosis-muted border border-gnosis-border hover:bg-gnosis-hover',
            ].join(' ')}
          >
            {m.charAt(0).toUpperCase() + m.slice(1)}
          </button>
        ))}
      </div>

      {/* Results */}
      {submitted && mode === 'semantic' ? (
        <SemanticSearch query={submitted} />
      ) : submitted ? (
        <SearchResults query={submitted} mode={mode} />
      ) : null}
    </div>
  );
}
