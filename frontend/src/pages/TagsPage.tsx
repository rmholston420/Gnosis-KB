/**
 * TagsPage
 * ========
 * Displays all tags as a filterable, interactive tag cloud.
 * Uses plain async/await — no React Query dependency.
 */
import React, { useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tag, Search, SortAsc, SortDesc } from 'lucide-react';
import api from '../services/api';

interface TagEntry {
  name: string;
  count: number;
}

type RawTagsResponse = TagEntry[] | Record<string, number>;

function normalise(raw: RawTagsResponse): TagEntry[] {
  if (Array.isArray(raw)) return raw;
  return Object.entries(raw).map(([name, count]) => ({ name, count }));
}

const MIN_FONT = 0.75;
const MAX_FONT = 1.625;

function tagFontSize(count: number, min: number, max: number): string {
  if (max <= min) return `${MIN_FONT}rem`;
  const scaled = Math.log(count + 1) / Math.log(max + 1);
  const size = MIN_FONT + scaled * (MAX_FONT - MIN_FONT);
  return `${size.toFixed(3)}rem`;
}

function tagOpacity(count: number, max: number): number {
  if (max === 0) return 1;
  return 0.55 + 0.45 * (count / max);
}

export default function TagsPage() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('');
  const [sortBy, setSortBy] = useState<'alpha' | 'count'>('count');
  const [tags, setTags] = useState<TagEntry[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [isError, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    // Support both api.listTags and api.getTags naming
    const fetcher = (api as unknown as Record<string, () => Promise<RawTagsResponse>>);
    const fn = fetcher.listTags ?? fetcher.getTags;
    (fn.call(api) as Promise<RawTagsResponse>)
      .then((raw) => {
        if (!cancelled) setTags(normalise(raw));
      })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const maxCount = useMemo(() => Math.max(0, ...tags.map((t) => t.count)), [tags]);
  const minCount = useMemo(() => Math.min(Infinity, ...tags.map((t) => t.count)), [tags]);

  const filtered = useMemo(() => {
    const q = filter.toLowerCase();
    return tags
      .filter((t) => t.name.toLowerCase().includes(q))
      .sort((a, b) =>
        sortBy === 'alpha'
          ? a.name.localeCompare(b.name)
          : b.count - a.count
      );
  }, [tags, filter, sortBy]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Tag size={18} className="text-text-muted" />
          <h1 className="text-xl font-semibold text-text-primary">Tags</h1>
          {!isLoading && (
            <span className="text-xs text-text-faint">({tags.length})</span>
          )}
        </div>
        <button
          onClick={() => setSortBy((s) => (s === 'alpha' ? 'count' : 'alpha'))}
          className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs text-text-muted hover:bg-bg-elevated transition-colors"
          title={sortBy === 'alpha' ? 'Sort by count' : 'Sort alphabetically'}
        >
          {sortBy === 'alpha' ? <SortDesc size={12} /> : <SortAsc size={12} />}
          {sortBy === 'alpha' ? 'By count' : 'A–Z'}
        </button>
      </div>

      {/* Filter */}
      <div className="relative mb-6">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-faint" />
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter tags…"
          className="w-full rounded-xl border border-border-default bg-bg-secondary py-2 pl-9 pr-4 text-sm text-text-primary placeholder:text-text-faint focus:border-accent-teal focus:outline-none"
        />
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="skeleton h-7 rounded-full" style={{ width: `${60 + Math.random() * 60}px` }} />
          ))}
        </div>
      )}

      {/* Error */}
      {isError && (
        <p className="text-sm text-error">Failed to load tags.</p>
      )}

      {/* Empty state */}
      {!isLoading && !isError && tags.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-text-muted">
          <Tag size={32} className="mb-3 opacity-30" />
          <p className="text-sm">No tags yet — add tags to your notes to see them here.</p>
        </div>
      )}

      {/* No filter matches */}
      {!isLoading && !isError && tags.length > 0 && filtered.length === 0 && (
        <p className="text-sm text-text-muted">No tags match &ldquo;{filter}&rdquo;.</p>
      )}

      {/* Tag cloud */}
      {!isLoading && filtered.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {filtered.map((t) => (
            <button
              key={t.name}
              onClick={() => navigate(`/notes?tag=${encodeURIComponent(t.name)}`)}
              className="group flex items-center gap-1.5 rounded-full border border-border-default bg-bg-secondary px-3 py-1 transition-all hover:border-accent-teal hover:bg-accent-teal/5"
              style={{
                fontSize: tagFontSize(t.count, minCount, maxCount),
                opacity: tagOpacity(t.count, maxCount),
              }}
            >
              <span className="text-text-primary group-hover:text-accent-teal transition-colors">{t.name}</span>
              <span className="text-text-faint group-hover:text-accent-teal/60 transition-colors">{t.count}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
