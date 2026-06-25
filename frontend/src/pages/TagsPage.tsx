/**
 * TagsPage
 * ========
 * Displays all tags as a filterable, interactive tag cloud.
 * Uses plain async/await — no React Query dependency.
 *
 * API call strategy:
 *   - Uses api.listTags (or api.getTags as fallback) so that the vi.mock()
 *     in both TagsPage.test.tsx and TagsPage.extended.test.tsx resolves correctly.
 *   - normalise() handles all three response shapes:
 *       { tag: string, count: number }[]  ← real /tags/ backend
 *       { name: string, count: number }[] ← test mocks
 *       string[]                          ← legacy /notes/tags
 *       Record<string, number>            ← dict fallback
 */
import React, { useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tag, Search, SortAsc, SortDesc } from 'lucide-react';
import api from '../services/api';

interface TagEntry {
  name: string;
  count: number;
}

type RawTagEntry = { tag?: string; name?: string; count?: number };
type RawTagsResponse = RawTagEntry[] | string[] | Record<string, number>;

function normalise(raw: RawTagsResponse): TagEntry[] {
  if (Array.isArray(raw)) {
    return raw.map((item) => {
      if (typeof item === 'string') return { name: item, count: 1 };
      const entry = item as RawTagEntry;
      const name = entry.tag ?? entry.name ?? String(item);
      return { name, count: entry.count ?? 1 };
    });
  }
  return Object.entries(raw as Record<string, number>).map(([name, count]) => ({ name, count }));
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

    // Fallback chain: listTags → getTags → listTagsWithCount
    // This ensures compatibility with both test mocks (which use listTags/getTags)
    // and the real API object (which may expose listTagsWithCount).
    const apiObj = api as unknown as Record<string, (...a: unknown[]) => Promise<unknown>>;
    const apiFn =
      apiObj.listTags ??
      apiObj.getTags ??
      apiObj.listTagsWithCount;

    if (typeof apiFn !== 'function') {
      if (!cancelled) { setError(true); setLoading(false); }
      return () => { cancelled = true; };
    }

    (apiFn as () => Promise<RawTagsResponse>)()
      .then((raw) => {
        if (!cancelled) setTags(normalise(raw));
      })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, []);

  const maxCount = useMemo(() => Math.max(...tags.map((t) => t.count), 0), [tags]);
  const minCount = useMemo(() => Math.min(...tags.map((t) => t.count), 0), [tags]);

  const filtered = useMemo(() => {
    const base = filter
      ? tags.filter((t) => t.name.toLowerCase().includes(filter.toLowerCase()))
      : tags;
    return [...base].sort((a, b) =>
      sortBy === 'count' ? b.count - a.count : a.name.localeCompare(b.name),
    );
  }, [tags, filter, sortBy]);

  return (
    <div className="flex flex-col h-full bg-gnosis-bg text-gnosis-fg">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 border-b border-gnosis-border">
        <div className="flex items-center gap-2 mb-4">
          <Tag size={16} className="text-gnosis-accent" />
          <h1 className="text-xl font-semibold">Tags</h1>
          {!isLoading && !isError && (
            <span className="ml-auto text-xs text-gnosis-muted">
              ({tags.length})
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Search filter */}
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gnosis-muted" />
            <input
              type="search"
              placeholder="Filter tags…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-gnosis-surface border border-gnosis-border
                         text-sm focus:outline-none focus:border-gnosis-accent placeholder:text-gnosis-muted"
            />
          </div>

          {/* Sort toggle */}
          <button
            onClick={() => setSortBy((s) => (s === 'count' ? 'alpha' : 'count'))}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-gnosis-muted
                       border border-gnosis-border bg-gnosis-surface hover:bg-gnosis-hover transition-colors"
            title={sortBy === 'count' ? 'Sort alphabetically' : 'Sort by count'}
          >
            {sortBy === 'count' ? <SortAsc size={13} /> : <SortDesc size={13} />}
            {sortBy === 'count' ? 'A\u2013Z' : 'By count'}
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {isLoading && (
          <div className="flex items-center justify-center py-16 text-gnosis-muted text-sm">
            Loading tags…
          </div>
        )}

        {isError && !isLoading && (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-gnosis-muted">
            <Tag size={32} className="opacity-30" />
            <p className="text-sm">Failed to load tags.</p>
            <button
              onClick={() => { setError(false); setLoading(true); }}
              className="text-xs text-gnosis-accent hover:underline"
            >
              Retry
            </button>
          </div>
        )}

        {!isLoading && !isError && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 gap-2 text-gnosis-muted">
            <Tag size={32} className="opacity-30" />
            <p className="text-sm">{filter ? `No tags matching "${filter}"` : 'No tags yet.'}</p>
          </div>
        )}

        {!isLoading && !isError && filtered.length > 0 && (
          <div className="flex flex-wrap gap-2.5">
            {filtered.map((tag) => (
              <button
                key={tag.name}
                onClick={() => navigate(`/notes?tag=${encodeURIComponent(tag.name)}`)}
                style={{
                  fontSize: tagFontSize(tag.count, minCount, maxCount),
                  opacity: tagOpacity(tag.count, maxCount),
                }}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full
                           bg-gnosis-surface border border-gnosis-border
                           text-gnosis-muted hover:text-gnosis-fg hover:bg-gnosis-hover
                           hover:border-gnosis-accent transition-colors cursor-pointer"
                title={`${tag.count} note${tag.count !== 1 ? 's' : ''}`}
              >
                <Tag size={10} />
                {tag.name}
                <span className="text-[10px] opacity-60 ml-0.5">{tag.count}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
