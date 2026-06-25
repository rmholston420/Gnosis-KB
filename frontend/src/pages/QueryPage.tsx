/**
 * QueryPage — RAG / structured query interface.
 *
 * Test contracts (QueryPage.test.tsx + QueryPage.extended.test.tsx):
 *
 * Basic (QueryPage.test.tsx):
 * - textarea placeholder /from folder where/i
 * - Run button disabled when empty, enabled when not
 * - Save button opens role="dialog"
 * - Dialog has Cancel button that closes it
 * - Example sidebar has "Draft Zettelkasten notes" item that fills textarea
 * - "No saved queries" empty state when axios.get returns []
 * - axios.post called on Run; shows /no results/i on empty rows
 * - shows /error/i on run failure
 *
 * Extended (QueryPage.extended.test.tsx):
 * - axios.get /api/queries on mount, displays saved query names
 * - Clicking a saved query name expands it (accordion) revealing inline Run btn
 * - Inline Run button inside accordion runs the query
 * - Red trash button inside expanded accordion calls axios.delete
 * - Save dialog confirm button labeled 'Save' (not 'Confirm')
 * - Save POSTs to /api/query/saved with { name, query }
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Trash2 } from 'lucide-react';

interface SavedQuery {
  id: number | string;
  name: string;
  query: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
}

interface QueryResult {
  rows: Record<string, unknown>[];
  total: number;
  query_time_ms: number;
}

const EXAMPLE_QUERIES = [
  {
    label: 'Draft Zettelkasten notes',
    query: "FROM notes WHERE note_type = 'fleeting' ORDER BY created_at DESC",
  },
  {
    label: 'Unlinked permanent notes',
    query: "FROM notes WHERE note_type = 'permanent' AND backlinks = 0",
  },
  {
    label: 'Notes tagged Buddhism',
    query: "FROM notes WHERE tags CONTAINS 'buddhism'",
  },
  {
    label: 'Recent daily notes',
    query: "FROM notes WHERE note_type = 'daily' LIMIT 10",
  },
];

export default function QueryPage() {
  const [queryText, setQueryText] = useState('');
  const [result, setResult] = useState<QueryResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  // Save dialog
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveName, setSaveName] = useState('');

  // Saved queries
  const [savedQueries, setSavedQueries] = useState<SavedQuery[]>([]);
  const [loadingQueries, setLoadingQueries] = useState(true);
  const [expandedId, setExpandedId] = useState<number | string | null>(null);

  // Load saved queries on mount
  useEffect(() => {
    axios
      .get<SavedQuery[]>('/api/queries')
      .then((res) => setSavedQueries(Array.isArray(res.data) ? res.data : []))
      .catch(() => setSavedQueries([]))
      .finally(() => setLoadingQueries(false));
  }, []);

  // ---- Run -----------------------------------------------------------------
  async function handleRun(query = queryText) {
    const q = query.trim();
    if (!q) return;
    setIsRunning(true);
    setRunError(null);
    setResult(null);
    try {
      const res = await axios.post<QueryResult>('/api/query/run', { query: q });
      setResult(res.data);
    } catch (err: unknown) {
      setRunError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsRunning(false);
    }
  }

  // ---- Save ----------------------------------------------------------------
  async function handleSaveConfirm() {
    if (!saveName.trim()) return;
    try {
      const res = await axios.post<SavedQuery>('/api/query/saved', {
        name: saveName,
        query: queryText,
      });
      setSavedQueries((prev) => [...prev, res.data]);
    } catch {
      // ignore
    }
    setShowSaveDialog(false);
    setSaveName('');
  }

  // ---- Delete saved query -------------------------------------------------
  async function handleDelete(id: number | string) {
    try {
      await axios.delete(`/api/query/saved/${id}`);
      setSavedQueries((prev) => prev.filter((q) => q.id !== id));
      if (expandedId === id) setExpandedId(null);
    } catch {
      // ignore
    }
  }

  return (
    <div className="flex h-full bg-gnosis-bg text-gnosis-fg">
      {/* ── Example / Saved sidebar ─────────────────────────────────────── */}
      <aside className="w-64 shrink-0 border-r border-gnosis-border px-4 py-6 overflow-y-auto">
        {/* Examples */}
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gnosis-muted mb-3">
          Examples
        </h2>
        <ul className="space-y-1">
          {EXAMPLE_QUERIES.map((ex) => (
            <li key={ex.label}>
              <button
                type="button"
                onClick={() => setQueryText(ex.query)}
                className="w-full text-left rounded px-2 py-1.5 text-xs text-gnosis-muted
                           hover:text-gnosis-fg hover:bg-gnosis-surface transition-colors"
              >
                {ex.label}
              </button>
            </li>
          ))}
        </ul>

        {/* Saved queries */}
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gnosis-muted mt-6 mb-3">
          Saved
        </h2>
        {loadingQueries ? (
          <p className="text-xs text-gnosis-muted">Loading…</p>
        ) : savedQueries.length === 0 ? (
          <p className="text-xs text-gnosis-muted">No saved queries</p>
        ) : (
          <ul className="space-y-1">
            {savedQueries.map((sq) => (
              <li key={sq.id} className="rounded border border-gnosis-border overflow-hidden">
                {/* Accordion header */}
                <button
                  type="button"
                  onClick={() =>
                    setExpandedId((prev) => (prev === sq.id ? null : sq.id))
                  }
                  className="w-full text-left px-2 py-1.5 text-xs text-gnosis-muted
                             hover:text-gnosis-fg hover:bg-gnosis-surface transition-colors"
                >
                  {sq.name}
                </button>

                {/* Accordion body */}
                {expandedId === sq.id && (
                  <div className="bg-gnosis-surface px-2 pb-2">
                    <pre className="text-xs text-gnosis-muted whitespace-pre-wrap break-all mb-2 mt-1">
                      {sq.query}
                    </pre>
                    <div className="flex gap-2 items-center">
                      <button
                        type="button"
                        onClick={() => {
                          setQueryText(sq.query);
                          void handleRun(sq.query);
                        }}
                        className="text-xs px-2 py-1 rounded bg-gnosis-accent text-white
                                   hover:opacity-90 transition-opacity"
                      >
                        Run
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDelete(sq.id)}
                        className="p-1 rounded text-red-500 hover:text-red-400 transition-colors"
                        aria-label="Delete saved query"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </aside>

      {/* ── Main query area ──────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col px-6 py-6 overflow-hidden">
        <h1 className="text-lg font-semibold text-gnosis-fg mb-4">Query</h1>

        {/* Textarea */}
        <textarea
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          placeholder="FROM folder WHERE tag = 'buddhism' ORDER BY modified_at DESC"
          rows={6}
          className="w-full rounded-md bg-gnosis-surface border border-gnosis-border px-3 py-2
                     text-gnosis-fg text-sm font-mono focus:outline-none focus:ring-2
                     focus:ring-gnosis-accent resize-none"
        />

        {/* Action buttons */}
        <div className="flex gap-2 mt-3">
          <button
            type="button"
            onClick={() => void handleRun()}
            disabled={!queryText.trim() || isRunning}
            className="px-4 py-2 rounded-md bg-gnosis-accent text-white text-sm font-medium
                       hover:opacity-90 transition-opacity
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {isRunning ? 'Running…' : 'Run'}
          </button>
          <button
            type="button"
            onClick={() => setShowSaveDialog(true)}
            className="px-4 py-2 rounded-md bg-gnosis-surface border border-gnosis-border
                       text-gnosis-fg text-sm font-medium hover:bg-gnosis-surface-2 transition-colors"
          >
            Save
          </button>
        </div>

        {/* Results */}
        <div className="mt-6 flex-1 overflow-y-auto">
          {isRunning && (
            <p className="text-sm text-gnosis-muted animate-pulse">Running query…</p>
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
                  {result.total} row{result.total !== 1 ? 's' : ''}
                  {' '}· {result.query_time_ms}ms
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-gnosis-border">
                        {Object.keys(result.rows[0]).map((col) => (
                          <th
                            key={col}
                            className="text-left px-3 py-2 text-gnosis-muted font-medium"
                          >
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.rows.map((row, i) => (
                        <tr
                          key={i}
                          className="border-b border-gnosis-border hover:bg-gnosis-surface"
                        >
                          {Object.values(row).map((cell, j) => (
                            <td key={j} className="px-3 py-2 text-gnosis-fg">
                              {String(cell ?? '')}
                            </td>
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

      {/* ── Save dialog ──────────────────────────────────────────────────── */}
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
              placeholder="Query name…"
              className="w-full rounded-md bg-gnosis-bg border border-gnosis-border px-3 py-2
                         text-gnosis-fg text-sm focus:outline-none focus:ring-2
                         focus:ring-gnosis-accent mb-4"
              autoFocus
            />
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => {
                  setShowSaveDialog(false);
                  setSaveName('');
                }}
                className="px-3 py-1.5 rounded text-xs text-gnosis-muted hover:text-gnosis-fg transition-colors"
              >
                Cancel
              </button>
              {/* Label is 'Save' — extended test uses within(dialog).getByRole('button', { name: /save/i }) */}
              <button
                type="button"
                onClick={() => void handleSaveConfirm()}
                disabled={!saveName.trim()}
                className="px-3 py-1.5 rounded bg-gnosis-accent text-white text-xs font-medium
                           hover:opacity-90 transition-opacity disabled:opacity-40"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
