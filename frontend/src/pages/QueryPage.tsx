/**
 * QueryPage — RAG / structured query interface.
 *
 * Test contracts (QueryPage.test.tsx + QueryPage.extended.test.tsx):
 * - textarea with placeholder matching /from folder where/i
 * - Run button: disabled when textarea empty, enabled when not
 * - Save button: opens a role="dialog" modal
 * - Dialog has a Cancel button that closes it
 * - Example sidebar contains "draft zettelkasten notes" clickable item
 *   that fills the textarea
 * - Saved queries section shows "No saved queries" when axios.get returns []
 * - Run button calls axios.post and shows "No results" on empty rows
 * - Shows /error/i text on run failure
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface SavedQuery {
  id: string;
  name: string;
  query: string;
}

interface QueryResult {
  rows: Record<string, unknown>[];
  total: number;
  query_time_ms: number;
}

const EXAMPLE_QUERIES = [
  { label: 'Draft Zettelkasten notes', query: 'FROM notes WHERE note_type = \'fleeting\' ORDER BY created_at DESC' },
  { label: 'Unlinked permanent notes', query: 'FROM notes WHERE note_type = \'permanent\' AND backlinks = 0' },
  { label: 'Notes tagged Buddhism',   query: 'FROM notes WHERE tags CONTAINS \'buddhism\'' },
  { label: 'Recent daily notes',      query: 'FROM notes WHERE note_type = \'daily\' LIMIT 10' },
];

export default function QueryPage() {
  const [queryText, setQueryText]       = useState('');
  const [result, setResult]             = useState<QueryResult | null>(null);
  const [runError, setRunError]         = useState<string | null>(null);
  const [isRunning, setIsRunning]       = useState(false);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveName, setSaveName]         = useState('');
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>([]);
  const [loadingQueries, setLoadingQueries] = useState(true);

  // Load saved queries on mount
  useEffect(() => {
    axios.get<SavedQuery[]>('/api/queries')
      .then((res) => setSavedQueries(Array.isArray(res.data) ? res.data : []))
      .catch(() => setSavedQueries([]))
      .finally(() => setLoadingQueries(false));
  }, []);

  async function handleRun() {
    if (!queryText.trim()) return;
    setIsRunning(true);
    setRunError(null);
    setResult(null);
    try {
      const res = await axios.post<QueryResult>('/api/query/run', { query: queryText });
      setResult(res.data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setRunError(msg);
    } finally {
      setIsRunning(false);
    }
  }

  async function handleSaveConfirm() {
    if (!saveName.trim()) return;
    try {
      const res = await axios.post<SavedQuery>('/api/queries', { name: saveName, query: queryText });
      setSavedQueries((prev) => [...prev, res.data]);
    } catch {
      // silently ignore save errors in this UI pass
    }
    setShowSaveDialog(false);
    setSaveName('');
  }

  function handleExampleClick(query: string) {
    setQueryText(query);
  }

  return (
    <div className="flex h-full bg-gnosis-bg text-gnosis-fg">
      {/* Example sidebar */}
      <aside className="w-64 shrink-0 border-r border-gnosis-border px-4 py-6 overflow-y-auto">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gnosis-muted mb-3">Examples</h2>
        <ul className="space-y-1">
          {EXAMPLE_QUERIES.map((ex) => (
            <li key={ex.label}>
              <button
                type="button"
                onClick={() => handleExampleClick(ex.query)}
                className="w-full text-left rounded px-2 py-1.5 text-xs text-gnosis-muted hover:text-gnosis-fg hover:bg-gnosis-surface transition-colors"
              >
                {ex.label}
              </button>
            </li>
          ))}
        </ul>

        {/* Saved queries */}
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gnosis-muted mt-6 mb-3">Saved</h2>
        {loadingQueries ? (
          <p className="text-xs text-gnosis-muted">Loading\u2026</p>
        ) : savedQueries.length === 0 ? (
          <p className="text-xs text-gnosis-muted">No saved queries</p>
        ) : (
          <ul className="space-y-1">
            {savedQueries.map((sq) => (
              <li key={sq.id}>
                <button
                  type="button"
                  onClick={() => handleExampleClick(sq.query)}
                  className="w-full text-left rounded px-2 py-1.5 text-xs text-gnosis-muted hover:text-gnosis-fg hover:bg-gnosis-surface transition-colors"
                >
                  {sq.name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      {/* Main query area */}
      <div className="flex-1 flex flex-col px-6 py-6 overflow-hidden">
        <h1 className="text-lg font-semibold text-gnosis-fg mb-4">Query</h1>

        {/* Textarea */}
        <textarea
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          placeholder="FROM folder WHERE tag = 'buddhism' ORDER BY modified_at DESC"
          rows={6}
          className="w-full rounded-md bg-gnosis-surface border border-gnosis-border px-3 py-2
                     text-gnosis-fg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-gnosis-accent
                     resize-none"
        />

        {/* Action buttons */}
        <div className="flex gap-2 mt-3">
          <button
            type="button"
            onClick={handleRun}
            disabled={!queryText.trim() || isRunning}
            className="px-4 py-2 rounded-md bg-gnosis-accent text-white text-sm font-medium
                       hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isRunning ? 'Running\u2026' : 'Run'}
          </button>
          <button
            type="button"
            onClick={() => setShowSaveDialog(true)}
            className="px-4 py-2 rounded-md bg-gnosis-surface border border-gnosis-border text-gnosis-fg text-sm font-medium
                       hover:bg-gnosis-surface-2 transition-colors"
          >
            Save
          </button>
        </div>

        {/* Results area */}
        <div className="mt-6 flex-1 overflow-y-auto">
          {isRunning && (
            <p className="text-sm text-gnosis-muted animate-pulse">Running query\u2026</p>
          )}
          {runError && (
            <p className="text-sm text-red-500">Query error: {runError}</p>
          )}
          {result && !runError && (
            result.rows.length === 0 ? (
              <p className="text-sm text-gnosis-muted">No results returned.</p>
            ) : (
              <div>
                <p className="text-xs text-gnosis-muted mb-2">
                  {result.total} row{result.total !== 1 ? 's' : ''} \u00b7 {result.query_time_ms}ms
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-gnosis-border">
                        {Object.keys(result.rows[0]).map((col) => (
                          <th key={col} className="text-left px-3 py-2 text-gnosis-muted font-medium">{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.rows.map((row, i) => (
                        <tr key={i} className="border-b border-gnosis-border hover:bg-gnosis-surface">
                          {Object.values(row).map((cell, j) => (
                            <td key={j} className="px-3 py-2 text-gnosis-fg">{String(cell ?? '')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )
          )}
        </div>
      </div>

      {/* Save dialog */}
      {showSaveDialog && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Save query"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
        >
          <div className="bg-gnosis-surface rounded-xl shadow-lg p-6 w-80">
            <h2 className="text-sm font-semibold text-gnosis-fg mb-4">Save Query</h2>
            <input
              type="text"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder="Query name\u2026"
              className="w-full rounded-md bg-gnosis-bg border border-gnosis-border px-3 py-2
                         text-gnosis-fg text-sm focus:outline-none focus:ring-2 focus:ring-gnosis-accent mb-4"
              autoFocus
            />
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => { setShowSaveDialog(false); setSaveName(''); }}
                className="px-3 py-1.5 rounded text-xs text-gnosis-muted hover:text-gnosis-fg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveConfirm}
                disabled={!saveName.trim()}
                className="px-3 py-1.5 rounded bg-gnosis-accent text-white text-xs font-medium
                           hover:opacity-90 transition-opacity disabled:opacity-40"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
