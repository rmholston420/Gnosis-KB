import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { SearchResponse } from '../types';
import { Loader2, Search } from 'lucide-react';

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState(searchParams.get('q') || '');

  const { data, isLoading } = useQuery<SearchResponse>({
    queryKey: ['search', query],
    queryFn: () => api.search(query) as Promise<SearchResponse>,
    enabled: query.length > 0,
  });

  useEffect(() => {
    if (query) setSearchParams({ q: query });
  }, [query]);

  return (
    <div className="p-4">
      <div className="flex items-center gap-2 mb-4">
        <div className="flex-1 flex items-center gap-2 bg-bg-tertiary rounded px-3 py-2">
          <Search size={14} className="text-text-muted" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your vault..."
            className="flex-1 bg-transparent text-sm text-text-primary outline-none placeholder-text-muted"
            autoFocus
          />
        </div>
      </div>

      {isLoading && (
        <div className="flex justify-center py-8">
          <Loader2 className="animate-spin text-text-muted" size={20} />
        </div>
      )}

      {data && (
        <div>
          <p className="text-xs text-text-muted mb-3">
            {data.total} result{data.total !== 1 ? 's' : ''} in {data.elapsed_ms.toFixed(0)}ms
          </p>
          <div className="space-y-2">
            {data.results.map((r) => (
              <button
                key={r.note_id}
                onClick={() => navigate(`/notes/${r.note_id}`)}
                className="w-full text-left p-3 bg-bg-secondary border border-border-subtle hover:border-border rounded transition-colors"
              >
                <div className="flex items-center justify-between mb-1">
                  <h3 className="text-sm font-medium text-text-primary">{r.title}</h3>
                  <span className="text-xs text-text-muted">{r.score.toFixed(3)}</span>
                </div>
                {r.highlight && (
                  <p className="text-xs text-text-secondary line-clamp-2">{r.highlight}</p>
                )}
                {r.tags.length > 0 && (
                  <div className="flex gap-1 mt-1.5">
                    {r.tags.slice(0, 3).map((t) => (
                      <span key={t} className="text-xs text-text-muted">#{t}</span>
                    ))}
                  </div>
                )}
              </button>
            ))}
            {data.results.length === 0 && query && (
              <p className="text-text-muted text-sm text-center py-8">No results for "{query}"</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
