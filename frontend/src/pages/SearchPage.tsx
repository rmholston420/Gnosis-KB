/**
 * SearchPage.tsx — full hybrid / semantic / keyword search UI.
 * Uses the hook layer (hooks/useSearch) so RTL tests can spy correctly.
 */
import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Search, Loader2, AlertCircle } from 'lucide-react';
import { useHybridSearch, useKeywordSearch } from '../hooks/useSearch';
import { SearchResults } from '../components/search/SearchResults';
import { SemanticSearch } from '../components/search/SemanticSearch';

type Mode = 'hybrid' | 'semantic' | 'keyword';

const MODES: { id: Mode; label: string }[] = [
  { id: 'hybrid',   label: 'Hybrid'   },
  { id: 'semantic', label: 'Semantic' },
  { id: 'keyword',  label: 'Keyword'  },
];

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [query, setQuery] = useState(searchParams.get('q') ?? '');
  const [mode, setMode]   = useState<Mode>('hybrid');

  useEffect(() => {
    const p = new URLSearchParams(searchParams);
    if (query) { p.set('q', query); } else { p.delete('q'); }
    setSearchParams(p, { replace: true });
  }, [query]); // eslint-disable-line

  const hybridResult  = useHybridSearch(query);
  const keywordResult = useKeywordSearch(query);
  const active = mode === 'keyword' ? keywordResult : hybridResult;
  const { data, isLoading, isError } = active;
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const handleResultClick = (noteId: string) => navigate(`/notes/${noteId}`);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <h1 className="text-xl font-semibold text-gnosis-fg">Search</h1>

      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gnosis-muted pointer-events-none" />
        <input
          type="search"
          role="searchbox"
          aria-label="Search vault"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search your vault…"
          className="w-full pl-9 pr-4 py-2.5 text-sm bg-gnosis-surface border border-gnosis-border rounded-lg text-gnosis-fg placeholder-gnosis-muted focus:outline-none focus:ring-2 focus:ring-gnosis-accent"
        />
      </div>

      <div role="tablist" className="flex gap-1 p-1 bg-gnosis-surface rounded-lg w-fit border border-gnosis-border">
        {MODES.map(({ id, label }) => (
          <button
            key={id}
            role="button"
            aria-pressed={mode === id}
            onClick={() => setMode(id)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              mode === id ? 'bg-gnosis-accent text-white' : 'text-gnosis-muted hover:text-gnosis-fg hover:bg-gnosis-hover'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === 'semantic' && <SemanticSearch />}

      {mode !== 'semantic' && (
        <>
          {isError && (
            <div className="flex items-center gap-2 text-sm text-red-400 p-3 rounded-lg border border-red-400/20">
              <AlertCircle size={15} /><span>Search failed — please try again.</span>
            </div>
          )}
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-gnosis-muted">
              <Loader2 size={14} className="animate-spin" /><span>Searching…</span>
            </div>
          )}
          {!isLoading && !isError && query && items.length === 0 && (
            <p className="text-sm text-gnosis-muted py-8 text-center">
              No results for <strong className="text-gnosis-fg">"{query}"</strong>
            </p>
          )}
          {/*
            SearchResults renders its own count paragraph internally.
            Do NOT add a duplicate count <p> here — tests call getByText(/N results/i)
            and would find two elements.
          */}
          {items.length > 0 && (
            <SearchResults
              results={items}
              query={query}
              isLoading={isLoading}
              isError={isError}
              total={total}
              onResultClick={handleResultClick}
            />
          )}
        </>
      )}
    </div>
  );
}
