/**
 * SearchPage — full-text, semantic and hybrid search UI.
 */
import React, { useState, useCallback, FormEvent } from 'react';
import { useSearch } from '../hooks/useSearch';
import type { SearchMode } from '../hooks/useSearch';
import { SearchResults } from '../components/search/SearchResults';
import { SemanticSearch } from '../components/search/SemanticSearch';

const MODES: { label: string; value: SearchMode }[] = [
  { label: 'Hybrid', value: 'hybrid' },
  { label: 'Semantic', value: 'semantic' },
  { label: 'Keyword', value: 'fulltext' },
];

export default function SearchPage() {
  const [inputValue, setInputValue] = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [mode, setMode] = useState<SearchMode>('hybrid');

  const { isLoading, isError, data } = useSearch(inputValue, mode);
  const items = data?.items ?? [];
  const total = data?.total ?? items.length;

  const handleSubmit = useCallback((e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmittedQuery(inputValue);
  }, [inputValue]);

  const handleInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  }, []);

  const isSemantic = mode === 'semantic';

  return (
    <div className="flex flex-col h-full bg-gnosis-bg text-gnosis-fg">
      <div className="px-6 pt-6 pb-4 border-b border-gnosis-border">
        <h1 className="text-xl font-semibold mb-3">Search</h1>

        {!isSemantic && (
          <form onSubmit={handleSubmit}>
            <input
              type="search"
              value={inputValue}
              onChange={handleInput}
              placeholder="Search your vault…"
              className="w-full rounded-lg bg-gnosis-surface border border-gnosis-border px-4 py-2 text-sm
                         focus:outline-none focus:border-gnosis-accent placeholder:text-gnosis-muted"
              autoFocus
            />
          </form>
        )}

        <div className="flex gap-2 mt-3" role="tablist">
          {MODES.map((m) => (
            <button
              key={m.value}
              role="tab"
              aria-selected={mode === m.value}
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

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {isSemantic ? (
          <SemanticSearch />
        ) : (
          <>
            {isLoading && <p className="text-sm text-gnosis-muted animate-pulse">Searching…</p>}
            {isError && <p className="text-sm text-red-500">Search failed.</p>}
            {!isLoading && !isError && items.length > 0 && (
              <>
                <p className="text-xs text-gnosis-muted mb-3">{total} results</p>
                <ul className="space-y-3">
                  {items.map((r) => (
                    <li
                      key={r.note_id}
                      className="rounded-lg border border-gnosis-border bg-gnosis-surface p-4 hover:border-gnosis-accent transition-colors cursor-pointer"
                    >
                      <h2 className="text-sm font-medium text-gnosis-fg">{r.title}</h2>
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
              </>
            )}
            {!isLoading && !isError && items.length === 0 && submittedQuery.trim().length > 0 && (
              <SearchResults query={submittedQuery} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
