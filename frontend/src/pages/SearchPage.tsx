/**
 * SearchPage
 * ==========
 * Multi-mode search: Hybrid (BM25 + vector), Semantic (vector-only), Keyword.
 * Reads the initial query from the `?q=` URL param.
 * Uses the canonical `useSearch` hook + `SearchResults` / `SemanticSearch` components.
 */
import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, Sparkles, Type } from 'lucide-react';
import { useHybridSearch, useKeywordSearch } from '../hooks/useSearch';
import { SearchResults }  from '../components/search/SearchResults';
import { SemanticSearch } from '../components/search/SemanticSearch';

type Mode = 'hybrid' | 'semantic' | 'keyword';

const MODE_TABS: { id: Mode; label: string; icon: React.ReactNode }[] = [
  { id: 'hybrid',   label: 'Hybrid',   icon: <Search   size={13} /> },
  { id: 'semantic', label: 'Semantic', icon: <Sparkles size={13} /> },
  { id: 'keyword',  label: 'Keyword',  icon: <Type     size={13} /> },
];

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(() => searchParams.get('q') ?? '');
  const [mode,  setMode]  = useState<Mode>('hybrid');

  // Sync query → URL param
  useEffect(() => {
    if (query.trim()) setSearchParams({ q: query }, { replace: true });
    else              setSearchParams({}, { replace: true });
  }, [query]);

  // Hybrid search
  const hybridResult  = useHybridSearch(mode === 'hybrid'  ? query : '');
  const keywordResult = useKeywordSearch(mode === 'keyword' ? query : '');

  // Pick the active result set
  const active = mode === 'hybrid'
    ? hybridResult
    : mode === 'keyword'
      ? keywordResult
      : { data: undefined, isLoading: false, isError: false };

  return (
    <div className="flex flex-col h-full">
      {/* Search bar */}
      <div className="flex-shrink-0 px-4 pt-4 pb-2 border-b border-border space-y-3">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="search"
            className="w-full pl-9 pr-4 py-2 text-sm bg-bg-tertiary border border-border rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:ring-1 focus:ring-accent-cyan"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search vault\u2026"
            aria-label="Search query"
            autoFocus
          />
        </div>

        {/* Mode tabs */}
        <div className="flex gap-1">
          {MODE_TABS.map(({ id, label, icon }) => (
            <button
              key={id}
              onClick={() => setMode(id)}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                mode === id
                  ? 'bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/30'
                  : 'text-text-muted hover:text-text-primary hover:bg-bg-elevated border border-transparent'
              }`}
              aria-pressed={mode === id}
            >
              {icon}
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Results area */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {mode === 'semantic' ? (
          <SemanticSearch />
        ) : (
          <SearchResults
            results={active.data?.items ?? []}
            query={query}
            isLoading={active.isLoading}
            isError={active.isError}
            total={active.data?.total}
          />
        )}
      </div>
    </div>
  );
}
