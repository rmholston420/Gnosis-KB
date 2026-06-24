import React, { useState, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play, Save, Trash2, ChevronDown, ChevronRight, Loader2, AlertCircle, Clock, Database } from 'lucide-react';
import axios from 'axios';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8010';

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

const EXAMPLES = [
  { label: 'Draft zettelkasten notes', query: 'FROM 10-zettelkasten WHERE status=draft SORT modified DESC LIMIT 20' },
  { label: 'Inbox (recent)', query: 'FROM 00-inbox SORT modified_at DESC LIMIT 10 SELECT title,status,modified_at' },
  { label: 'Active projects', query: 'FROM 20-projects WHERE note_type=project SORT modified DESC' },
  { label: 'EEG-tagged notes', query: 'WHERE tags CONTAINS eeg SORT created_at DESC' },
  { label: 'Long notes (>200 words)', query: 'WHERE word_count > 200 SORT word_count DESC LIMIT 30 SELECT title,word_count,folder' },
  { label: 'Needs review (last 7 days)', query: 'FROM 10-zettelkasten WHERE status=evergreen SORT last_reviewed ASC LIMIT 20 SELECT title,last_reviewed,folder' },
];

function ResultTable({ result }: { result: QueryResult }) {
  if (result.rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-400">
        <Database size={40} className="mb-3 opacity-40" />
        <p className="text-sm">No results matched your query.</p>
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
    <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-xl bg-white dark:bg-gray-900 shadow-2xl p-6 space-y-4">
        <h2 className="text-base font-semibold">Save Query</h2>
        <input
          placeholder="Name"
          value={name}
          onChange={e => setName(e.target.value)}
          className="w-full rounded border border-gray-200 dark:border-gray-700 bg-transparent px-3 py-2 text-sm focus:outline-none"
        />
        <textarea
          placeholder="Description (optional)"
          value={desc}
          onChange={e => setDesc(e.target.value)}
          rows={2}
          className="w-full rounded border border-gray-200 dark:border-gray-700 bg-transparent px-3 py-2 text-sm focus:outline-none resize-none"
        />
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700">Cancel</button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!name.trim() || mutation.isPending}
            className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {mutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function QueryPage() {
  const queryClient = useQueryClient();
  const [queryText, setQueryText]   = useState('');
  const [result, setResult]         = useState<QueryResult | null>(null);
  const [error, setError]           = useState<string | null>(null);
  const [showSave, setShowSave]     = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const textareaRef                 = useRef<HTMLTextAreaElement>(null);

  const runMutation = useMutation({
    mutationFn: () => api.runQuery(queryText),
    onSuccess: (data) => { setResult(data); setError(null); },
    onError: (err) => setError(err instanceof Error ? err.message : 'Query failed'),
  });

  const { data: saved = [] } = useQuery<SavedDashboard[]>({
    queryKey: ['saved-queries'],
    queryFn:  api.listSaved,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteSaved(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['saved-queries'] }),
  });

  const runSavedMutation = useMutation({
    mutationFn: (id: number) => api.runSaved(id),
    onSuccess: (data) => { setResult(data); setError(null); },
    onError: (err) => setError(err instanceof Error ? err.message : 'Query failed'),
  });

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runMutation.mutate();
    }
  }, [runMutation]);

  return (
    <div className="flex h-full min-h-0 overflow-hidden">
      <div className="w-64 flex-shrink-0 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 flex flex-col overflow-hidden">
        <div className="px-3 py-3 border-b border-gray-200 dark:border-gray-800">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Examples</p>
          <div className="space-y-1">
            {EXAMPLES.map((ex) => (
              <button
                key={ex.label}
                onClick={() => setQueryText(ex.query)}
                className="w-full text-left rounded px-2 py-1.5 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors truncate"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Saved</p>
          {saved.length === 0 && (
            <p className="text-xs text-gray-400 italic">No saved queries yet.</p>
          )}
          {saved.map((s) => (
            <div key={s.id} className="mb-1 rounded border border-gray-200 dark:border-gray-800 overflow-hidden">
              <button
                onClick={() => setExpandedId(expandedId === s.id ? null : s.id)}
                className="w-full flex items-center gap-2 px-2 py-2 text-left hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
              >
                {expandedId === s.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <span className="flex-1 text-xs font-medium truncate">{s.name}</span>
              </button>
              {expandedId === s.id && (
                <div className="px-2 pb-2 space-y-2 border-t border-gray-100 dark:border-gray-800">
                  <p className="text-[11px] text-gray-500">{s.description}</p>
                  <div className="flex gap-1">
                    <button
                      onClick={() => runSavedMutation.mutate(s.id)}
                      className="flex-1 rounded bg-blue-600 text-white px-2 py-1 text-[11px] hover:bg-blue-700"
                    >
                      Run
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(s.id)}
                      className="rounded border border-red-200 text-red-600 px-2 py-1 hover:bg-red-50"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 min-w-0 flex flex-col bg-gray-50 dark:bg-gray-950">
        <div className="border-b border-gray-200 dark:border-gray-800 px-6 py-4 bg-white dark:bg-gray-950">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h1 className="text-base font-semibold">Query Builder</h1>
              <p className="text-xs text-gray-400 mt-0.5">Run SQL-like queries against your note index</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowSave(true)}
                className="flex items-center gap-1 rounded px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-900"
              >
                <Save size={14} /> Save
              </button>
              <button
                onClick={() => runMutation.mutate()}
                disabled={!queryText.trim() || runMutation.isPending}
                className="flex items-center gap-1 rounded bg-blue-600 text-white px-3 py-1.5 text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                {runMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                Run
              </button>
            </div>
          </div>

          <textarea
            ref={textareaRef}
            value={queryText}
            onChange={e => setQueryText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="FROM folder WHERE status = draft SORT modified DESC LIMIT 20"
            className="w-full min-h-[132px] resize-y rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-4 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            spellCheck={false}
          />
          <p className="mt-2 text-[11px] text-gray-400">Tip: Press Ctrl/Cmd + Enter to run</p>
        </div>

        <div className="flex-1 overflow-auto p-6">
          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-900/10 dark:text-red-400">
              <AlertCircle size={16} /> Error: {error}
            </div>
          )}

          {!result && !runMutation.isPending && !error && (
            <div className="h-full flex items-center justify-center text-center text-gray-400">
              <div>
                <Database size={40} className="mx-auto mb-3 opacity-40" />
                <p className="text-sm">Run a query to inspect your notes.</p>
              </div>
            </div>
          )}

          {result && <ResultTable result={result} />}
        </div>
      </div>

      {showSave && (
        <SaveDialog
          query={queryText}
          onClose={() => setShowSave(false)}
          onSaved={() => queryClient.invalidateQueries({ queryKey: ['saved-queries'] })}
        />
      )}
    </div>
  );
}
