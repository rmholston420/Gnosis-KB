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

  return <div className="p-4">Search</div>;
}
