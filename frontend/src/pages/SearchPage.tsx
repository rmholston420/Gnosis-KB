/**
 * SearchPage — full-text, semantic and hybrid search UI.
 *
 * Contract (enforced by SearchPage.extended.test.tsx):
 *  - useSearch is called with (inputValue, mode) on every render
 *  - On form submit with a non-empty query:
 *    - isError  → SINGLE element matching /search failed/i
 *    - 0 items  → SINGLE element matching /no results/i
 *    - items    → headings + '/N results/' count badge
 *  - No duplicate empty-state elements; getByText must find exactly one match.
 *  - SemanticSearch renders when mode === 'semantic'
 */
import React, { useState, useCallback, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSearch } from '../hooks/useSearch';
import type { SearchMode } from '../hooks/useSearch';
import { SemanticSearch } from '../components/search/SemanticSearch';

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

  // ── Results body ───────────────────────────────────────────────────────────
  // Each branch returns EXACTLY ONE root element (or null) to prevent
  // duplicate text nodes that break getByText() assertions.
  function renderBody() {
    if (isSemantic) return <SemanticSearch />;
    if (!submittedQuery.trim()) return null;
    if (isLoading) {
      return <p className="text-sm text-gnosis-muted">Searching\u2026</p>;
    }
    if (isError) {
      return (
        <p className="text-sm text-gnosis-error" role="alert">
          Search failed. Please try again.
        </p>
      );
    }
    if (items.length === 0) {
      return (
        <p className="text-sm text-gnosis-muted">
          No results for &#x201c;{submittedQuery}&#x201d;.
        </p>
      );
    }
    return (
      <div>
        <p className="text-xs text-gnosis-muted mb-3">{total} results</p>
        <ul className="space-y-2">
          {items.map((item) => {
            const id      = (item as { note_id?: string }).note_id ?? (item as { id?: string }).id ?? '';
            const title   = (item as { title?: string }).title ?? '';
            const snippet = (item as { snippet?: string; excerpt?: string }).snippet
              ?? (item as { excerpt?: string }).excerpt
              ?? '';
            return (
              <li key={id}>
                <button
                  type="button"
                  className="w-full text-left rounded-lg p-3 bg-gnosis-surface border border-gnosis-border hover:bg-gnosis-hover transition-colors"
                  onClick={() => id && navigate(`/notes/${id}`)}
                >
                  <h3 className="font-medium text-gnosis-fg text-sm">{title}</h3>
                  {snippet && (
                    <p className="text-xs text-gnosis-muted mt-0.5 line-clamp-2">{snippet}</p>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
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
