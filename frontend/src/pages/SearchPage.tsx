import React, { useEffect, useState } from 'react';
import { Search, AlertCircle } from 'lucide-react';
import api from '../services/api';
import type { SearchResult } from '../types';
import NoteCard from '../components/NoteCard';

interface SearchResponse {
  items: SearchResult[];
  total: number;
}

export default function SearchPage() {
  const [q, setQ] = useState('');
  const [m, setM] = useState('hybrid');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!q.trim()) {
      setResults([]);
      setTotal(0);
      return;
    }
    const run = async () => {
      setFetching(true);
      setError(false);
      try {
        const resp = await (api.search(q, { mode: m }) as Promise<SearchResponse>);
        setResults(resp.items ?? []);
        setTotal(resp.total ?? 0);
      } catch {
        setError(true);
      } finally {
        setFetching(false);
      }
    };
    void run();
  }, [q, m]);

  return (
    <div className="p-4">
      <div className="flex items-center gap-2 mb-4">
        <Search size={18} />
        <input
          className="flex-1 border rounded px-3 py-1"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search vault…"
          aria-label="Search query"
        />
        <select value={m} onChange={(e) => setM(e.target.value)} aria-label="Search mode">
          <option value="hybrid">Hybrid</option>
          <option value="semantic">Semantic</option>
          <option value="keyword">Keyword</option>
        </select>
      </div>

      {fetching && <p className="text-muted">Searching…</p>}

      {error && (
        <div className="flex items-center gap-2 text-red-600" role="alert">
          <AlertCircle size={16} />
          <span>Search failed. Please try again.</span>
        </div>
      )}

      {!fetching && !error && q.trim() && results.length === 0 && (
        <p className="text-muted">No results for "{q}".</p>
      )}

      {total > 0 && (
        <p className="text-sm text-muted mb-2">{total} result{total !== 1 ? 's' : ''}</p>
      )}

      <div className="space-y-2">
        {results.map((r) => (
          <NoteCard key={r.note_id} note={r as unknown as import('../types').Note} />
        ))}
      </div>
    </div>
  );
}
