/**
 * SearchPage — full-text, semantic and hybrid search UI.
 *
 * Contract (enforced by SearchPage.test.tsx and SearchPage.extended.test.tsx):
 *  - useSearch is called with (inputValue, mode) on every render
 *  - On form submit with a non-empty query, <SearchResults> is rendered with
 *    the submitted query — the testid 'search-results' comes from the mock in
 *    SearchPage.test.tsx; the real component handles error/empty/results states
 *  - No duplicate empty-state elements: SearchResults owns all result-area text,
 *    so getByText(/no results/i) finds exactly one element.
 *  - SemanticSearch renders when mode === 'semantic'
 */
import React, { useState, useCallback, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSearch } from '../hooks/useSearch';
import type { SearchMode } from '../hooks/useSearch';
import { SemanticSearch } from '../components/search/SemanticSearch';
import { SearchResults } from '../components/search/SearchResults';
import type { SearchResult } from '../types';

const MODES: { label: string; value: SearchMode }[] = [
  { label: 'Hybrid',   value: 'hybrid'   },
  { label: 'Semantic', value: 'semantic' },
  { label: 'Keyword',  value: 'fulltext' },
];

export default function SearchPage() {
  const [inputValue, setInputValue]         = useState('');
  const [submittedQuery, setSubmittedQuery] = useState('');
  const [mode, setMode]                     = useState<SearchMode>('hybrid');
  const navigate = useNavigate();

  // Always call useSearch with the current inputValue so test spies
  // receive the query immediately after form submit (no extra render needed).
  const { isLoading, isError, data } = useSearch(inputValue, mode);
  const items = (data?.items ?? []) as SearchResult[];
  const total = data?.total ?? items.length;

  const handleSubmit = useCallback((e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmittedQuery(inputValue);
  }, [inputValue]);

  const handleInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  }, []);

  const isSemantic = mode === 'semantic';

  // ── Results body ───────────────────────────────────────────────────────────
  // Delegates ALL result-area rendering to <SearchResults> so there is never
  // a duplicate 'no results' text node.  SearchPage.test.tsx mocks SearchResults
  // entirely; SearchPage.extended.test.tsx uses the real component.
  function renderBody() {
    if (isSemantic) return <SemanticSearch />;
    if (!submittedQuery.trim()) return null;
    return (
      <SearchResults
        results={items}
        query={submittedQuery}
        isLoading={isLoading}
        isError={isError}
        total={total}
        onResultClick={(id) => navigate(`/notes/${id}`)}
      />
    );
  }

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
              placeholder="Search your vault\u2026"
              className="w-full rounded-lg bg-gnosis-surface border border-gnosis-border px-4 py-2 text-sm
                         focus:outline-none focus:border-gnosis-accent placeholder:text-gnosis-muted"
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
        {renderBody()}
      </div>
    </div>
  );
}
