/**
 * SearchPage — hybrid, semantic, keyword, and fulltext search UI.
 *
 * SemanticSearch accepts only `seedNoteId` (not `query`) — it owns its own
 * query input internally.
 * SearchResults accepts `results`, `query`, `isLoading`, `isError`,
 * `total`, and `onResultClick` — not a bare `query` + `mode`.
 * We use useSearch here directly and pass the resolved results down.
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { SearchResults } from '../components/search/SearchResults';
import { SemanticSearch } from '../components/search/SemanticSearch';
import { useSearch } from '../hooks/useSearch';
import type { SearchMode } from '../hooks/useSearch';

const MODES: { value: SearchMode; label: string }[] = [
  { value: 'hybrid',   label: 'Hybrid' },
  { value: 'semantic', label: 'Semantic' },
  { value: 'keyword',  label: 'Keyword' },
  { value: 'fulltext', label: 'Fulltext' },
];

export default function SearchPage() {
  const [query, setQuery]         = useState('');
  const [mode, setMode]           = useState<SearchMode>('hybrid');
  const [submitted, setSubmitted] = useState('');
  const navigate = useNavigate();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(query);
  };

  const { data, isLoading, isError } = useSearch(
    mode !== 'semantic' ? submitted : '',
    mode !== 'semantic' ? mode : 'hybrid',
  );

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gnosis-fg mb-6">Search</h1>

      {mode !== 'semantic' && (
        <form onSubmit={handleSearch} className="flex gap-2 mb-4">
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your vault\u2026"
            className="flex-1 rounded-lg border border-gnosis-border bg-gnosis-surface px-3 py-2 text-sm text-gnosis-fg placeholder:text-gnosis-muted focus:outline-none focus:ring-2 focus:ring-gnosis-accent"
          />
          <button
            type="submit"
            className="px-4 py-2 rounded-lg bg-gnosis-accent text-white text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Search
          </button>
        </form>
      )}

      <div className="flex gap-1 mb-6" role="tablist" aria-label="Search modes">
        {MODES.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={mode === value}
            onClick={() => setMode(value)}
            className={[
              'px-3 py-1 rounded-md text-xs font-medium transition-colors',
              mode === value
                ? 'bg-gnosis-accent text-white'
                : 'bg-gnosis-surface text-gnosis-muted border border-gnosis-border hover:bg-gnosis-hover',
            ].join(' ')}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === 'semantic' ? (
        <SemanticSearch />
      ) : submitted ? (
        <SearchResults
          results={data?.items ?? []}
          query={submitted}
          isLoading={isLoading}
          isError={isError}
          total={data?.total}
          onResultClick={(noteId) => navigate(`/notes/${noteId}`)}
        />
      ) : null}
    </div>
  );
}
