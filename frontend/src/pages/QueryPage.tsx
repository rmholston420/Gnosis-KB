import React, { useState, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play, Save, Trash2, ChevronDown, ChevronRight, Loader2, AlertCircle, Clock, Database } from 'lucide-react';
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

// ---- Main component ------------------------------------------------------

export default function QueryPage() {
  const queryClient = useQueryClient();
  const [queryText, setQueryText]   = useState(EXAMPLES[0].query);
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
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0 border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 flex flex-col overflow-hidden">
        {/* Examples */}
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

        {/* Saved */}
        <div className="flex-1 overflow-y-auto px-3 py-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Saved</p>
          {saved.length === 0 && (
            <p className="text-xs text-gray-400 italic">No saved queries yet.</p>
          )}
          {saved.map((s) => (
            <div key={s.id} className="mb-1 rounded border border-gray-100 dark:border-gray-800">
              <button
                onClick={() => setExpandedId(expandedId === s.id ? null : s.id)}
                className="w-full flex items-center gap-1.5 px-2 py-1.5 text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                {expandedId === s.id ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                <span className="truncate flex-1 text-left">{s.name}</span>
              </button>
              {expandedId === s.id && (
                <div className="px-2 pb-2 space-y-1.5">
                  {s.description && (
                    <p className="text-xs text-gray-400">{s.description}</p>
                  )}
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => runSavedMutation.mutate(s.id)}
                      className="flex items-center gap-1 rounded bg-blue-600 px-2 py-1 text-xs text-white hover:bg-blue-700"
                    >
                      <Play size={10} /> Run
                    </button>
                    <button
                      onClick={() => setQueryText(s.query)}
                      className="flex items-center gap-1 rounded bg-gray-100 dark:bg-gray-800 px-2 py-1 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-200"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(s.id)}
                      className="ml-auto rounded px-1.5 py-1 text-xs text-gray-400 hover:text-red-500 transition-colors"
                      aria-label="Delete saved query"
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Main area */}
      <div className="flex flex-1 min-w-0 flex-col overflow-hidden">
        {/* Editor */}
        <div className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
          <div className="px-4 py-3">
            <textarea
              ref={textareaRef}
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="FROM folder WHERE condition SORT field LIMIT n SELECT columns"
              rows={3}
              className="w-full resize-none rounded-lg border border-gray-200 dark:border-gray-700 bg-transparent px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex items-center gap-2 px-4 pb-3">
            <button
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending || !queryText.trim()}
              className="flex items-center gap-1.5 rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {runMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
              Run <span className="text-blue-200 text-xs ml-1">⌘↵</span>
            </button>
            <button
              onClick={() => setShowSave(true)}
              disabled={!queryText.trim()}
              className="flex items-center gap-1.5 rounded border border-gray-200 dark:border-gray-700 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
            >
              <Save size={14} /> Save
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-auto bg-white dark:bg-gray-950 p-4">
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/20 px-4 py-3 text-sm text-red-600 dark:text-red-400 mb-4">
              <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {result && <ResultTable result={result} />}
          {!result && !error && !runMutation.isPending && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-400">
              <Database size={40} className="opacity-20" />
              <p className="text-sm">Run a query to see results</p>
              <p className="text-xs opacity-60">Press ⌘↵ or click Run</p>
            </div>
          )}
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
