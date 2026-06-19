import React, { useState, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play, Save, Trash2, Plus, ChevronDown, ChevronRight, Loader2, AlertCircle, Clock, Database } from 'lucide-react';
import axios from 'axios';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8010';

// ---- Types ---------------------------------------------------------------

interface QueryResult {
  rows: Record<string, unknown>[];
  total: number;
  query_time_ms: number;
}

interface SavedDashboard {
  id: number;
  name: string;
  query: string;
  description: string;
  created_at: string;
  updated_at: string;
}

// ---- API helpers ---------------------------------------------------------

const api = {
  runQuery: (query: string): Promise<QueryResult> =>
    axios.post(`${API}/api/v1/query/run`, { query }).then(r => r.data),
  listSaved: (): Promise<SavedDashboard[]> =>
    axios.get(`${API}/api/v1/query/saved`).then(r => r.data),
  createSaved: (payload: { name: string; query: string; description: string }): Promise<SavedDashboard> =>
    axios.post(`${API}/api/v1/query/saved`, payload).then(r => r.data),
  deleteSaved: (id: number): Promise<void> =>
    axios.delete(`${API}/api/v1/query/saved/${id}`).then(() => undefined),
  runSaved: (id: number): Promise<QueryResult> =>
    axios.post(`${API}/api/v1/query/saved/${id}/run`).then(r => r.data),
};

// ---- Example queries shown in the sidebar --------------------------------

const EXAMPLES = [
  { label: 'Draft zettelkasten notes', query: 'FROM 10-zettelkasten WHERE status=draft SORT modified DESC LIMIT 20' },
  { label: 'Inbox (recent)', query: 'FROM 00-inbox SORT modified_at DESC LIMIT 10 SELECT title,status,modified_at' },
  { label: 'Active projects', query: 'FROM 20-projects WHERE note_type=project SORT modified DESC' },
  { label: 'EEG-tagged notes', query: 'WHERE tags CONTAINS eeg SORT created_at DESC' },
  { label: 'Long notes (>200 words)', query: 'WHERE word_count > 200 SORT word_count DESC LIMIT 30 SELECT title,word_count,folder' },
  { label: 'Needs review (last 7 days)', query: 'FROM 10-zettelkasten WHERE status=evergreen SORT last_reviewed ASC LIMIT 20 SELECT title,last_reviewed,folder' },
];

// ---- ResultTable component -----------------------------------------------

function ResultTable({ result }: { result: QueryResult }) {
  if (result.rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-400">
        <Database size={40} className="mb-3 opacity-40" />
        <p className="text-sm">No notes matched your query.</p>
      </div>
    );
  }

  const cols = Object.keys(result.rows[0]);

  return (
    <div className="overflow-x-auto">
      <div className="flex items-center gap-3 px-1 pb-2 text-xs text-gray-400">
        <span>{result.total} row{result.total !== 1 ? 's' : ''}</span>
        <span>·</span>
        <Clock size={12} />
        <span>{result.query_time_ms} ms</span>
      </div>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b border-gray-200 dark:border-gray-700">
            {cols.map(col => (
              <th
                key={col}
                className="text-left py-2 px-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider"
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
              className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            >
              {cols.map(col => {
                const val = row[col];
                let display: React.ReactNode = val === null || val === undefined ? <span className="text-gray-300">—</span> : String(val);
                if (col === 'title') {
                  display = <span className="font-medium text-blue-600 dark:text-blue-400">{String(val)}</span>;
                } else if (col === 'status') {
                  const colors: Record<string, string> = {
                    draft: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
                    evergreen: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
                    'in-progress': 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
                  };
                  display = (
                    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${colors[String(val)] ?? 'bg-gray-100 text-gray-600'}`}>
                      {String(val)}
                    </span>
                  );
                } else if (typeof val === 'string' && val.includes('T') && val.includes(':')) {
                  // ISO datetime — show only date part
                  display = <span className="text-gray-500">{val.slice(0, 10)}</span>;
                }
                return <td key={col} className="py-2 px-3 align-top">{display}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---- SaveDialog component ------------------------------------------------

function SaveDialog({
  query,
  onClose,
  onSaved,
}: {
  query: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const mutation = useMutation({
    mutationFn: () => api.createSaved({ name, query, description: desc }),
    onSuccess: () => { onSaved(); onClose(); },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white dark:bg-gray-900 shadow-2xl p-6 space-y-4">
        <h2 className="text-lg font-semibold">Save Dashboard</h2>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">Name</label>
            <input
              autoFocus
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Draft EEG notes"
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Description (optional)</label>
            <input
              value={desc}
              onChange={e => setDesc(e.target.value)}
              placeholder="What does this dashboard show?"
              className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800 px-3 py-2 font-mono text-xs text-gray-500 break-all">
            {query}
          </div>
        </div>
        {mutation.error && (
          <p className="text-sm text-red-500">{(mutation.error as Error).message}</p>
        )}
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800">
            Cancel
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!name.trim() || mutation.isPending}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---- Main Page -----------------------------------------------------------

export default function QueryPage() {
  const qc = useQueryClient();
  const [queryText, setQueryText] = useState(EXAMPLES[0].query);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSave, setShowSave] = useState(false);
  const [savedExpanded, setSavedExpanded] = useState(true);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const { data: saved = [] } = useQuery({
    queryKey: ['saved-queries'],
    queryFn: api.listSaved,
  });

  const runMutation = useMutation({
    mutationFn: () => api.runQuery(queryText),
    onSuccess: (data) => { setResult(data); setError(null); },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Query failed.';
      setError(msg);
      setResult(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteSaved(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['saved-queries'] }),
  });

  const runSavedMutation = useMutation({
    mutationFn: (id: number) => api.runSaved(id),
    onSuccess: (data) => { setResult(data); setError(null); },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Query failed.';
      setError(msg);
    },
  });

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      runMutation.mutate();
    }
  }, [runMutation]);

  return (
    <div className="flex h-full">
      {/* ---- Left sidebar ---- */}
      <aside className="flex w-64 flex-shrink-0 flex-col border-r border-gray-200 dark:border-gray-800 overflow-y-auto">
        {/* Examples */}
        <div className="p-3 border-b border-gray-100 dark:border-gray-800">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">Examples</p>
          <div className="space-y-1">
            {EXAMPLES.map(ex => (
              <button
                key={ex.label}
                onClick={() => setQueryText(ex.query)}
                className="w-full text-left rounded-lg px-2 py-1.5 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors truncate"
                title={ex.query}
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        {/* Saved dashboards */}
        <div className="p-3">
          <button
            onClick={() => setSavedExpanded(v => !v)}
            className="flex w-full items-center gap-1 text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2"
          >
            {savedExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            Saved Dashboards ({saved.length})
          </button>
          {savedExpanded && (
            <div className="space-y-1">
              {saved.length === 0 && (
                <p className="text-xs text-gray-400 px-2">No saved dashboards yet.</p>
              )}
              {saved.map(sq => (
                <div
                  key={sq.id}
                  className="group flex items-center gap-1 rounded-lg px-2 py-1.5 hover:bg-gray-100 dark:hover:bg-gray-800"
                >
                  <button
                    onClick={() => {
                      setQueryText(sq.query);
                      runSavedMutation.mutate(sq.id);
                    }}
                    className="flex-1 text-left text-xs text-gray-700 dark:text-gray-300 truncate"
                    title={sq.query}
                  >
                    {sq.name}
                  </button>
                  <button
                    onClick={() => deleteMutation.mutate(sq.id)}
                    className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-opacity"
                    title="Delete"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* ---- Main panel ---- */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Query editor */}
        <div className="border-b border-gray-200 dark:border-gray-800 p-4">
          <div className="flex items-start gap-2">
            <textarea
              ref={textareaRef}
              value={queryText}
              onChange={e => setQueryText(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={3}
              spellCheck={false}
              placeholder="FROM 10-zettelkasten WHERE status=draft SORT modified DESC LIMIT 20"
              className="flex-1 resize-none rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex flex-col gap-2">
              <button
                onClick={() => runMutation.mutate()}
                disabled={runMutation.isPending || !queryText.trim()}
                className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-sm text-white font-medium hover:bg-blue-700 disabled:opacity-50"
                title="Run query (Ctrl+Enter)"
              >
                {runMutation.isPending
                  ? <Loader2 size={15} className="animate-spin" />
                  : <Play size={15} />}
                Run
              </button>
              <button
                onClick={() => setShowSave(true)}
                disabled={!queryText.trim()}
                className="flex items-center gap-1.5 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
                title="Save as dashboard"
              >
                <Save size={15} />
                Save
              </button>
            </div>
          </div>
          {error && (
            <div className="mt-2 flex items-start gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 px-3 py-2 text-sm text-red-600 dark:text-red-400">
              <AlertCircle size={15} className="mt-0.5 flex-shrink-0" />
              <span className="font-mono">{error}</span>
            </div>
          )}
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-4">
          {!result && !runMutation.isPending && (
            <div className="flex flex-col items-center justify-center h-full text-gray-300 dark:text-gray-600">
              <Database size={48} className="mb-3" />
              <p className="text-sm">Run a query to see results</p>
              <p className="text-xs mt-1">Ctrl+Enter to run</p>
            </div>
          )}
          {runMutation.isPending && (
            <div className="flex items-center justify-center h-32">
              <Loader2 size={24} className="animate-spin text-blue-500" />
            </div>
          )}
          {result && !runMutation.isPending && <ResultTable result={result} />}
        </div>
      </div>

      {showSave && (
        <SaveDialog
          query={queryText}
          onClose={() => setShowSave(false)}
          onSaved={() => qc.invalidateQueries({ queryKey: ['saved-queries'] })}
        />
      )}
    </div>
  );
}
