/**
 * TagsPage
 * ========
 * Displays all tags from GET /api/v1/tags/ as a filterable, interactive tag
 * cloud.  Clicking any tag navigates to the notes list pre-filtered by that
 * tag via /notes?tag=<tag>.
 *
 * Font size of each tag pill scales logarithmically with note count so
 * frequently-used tags are visually prominent without drowning the rest.
 *
 * Features
 * --------
 * - Live filter input — instantly hides non-matching tags
 * - Sort toggle: alphabetical ↔ by note count
 * - Empty state for zero tags or zero filter matches
 * - Skeleton loader while fetching
 */

import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Tag, Search, SortAsc, SortDesc, Hash } from 'lucide-react';
import api from '../services/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TagEntry {
  tag: string;
  count: number;
}

type TagsResponse = TagEntry[] | Record<string, number>;

function normalise(raw: TagsResponse): TagEntry[] {
  if (Array.isArray(raw)) return raw;
  // Backend may return { tag: count } map
  return Object.entries(raw).map(([tag, count]) => ({ tag, count }));
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MIN_FONT = 0.75;  // rem
const MAX_FONT = 1.625; // rem

function tagFontSize(count: number, min: number, max: number): string {
  if (max <= min) return `${MIN_FONT}rem`;
  // log scale: ln(count) / ln(max)
  const scaled = Math.log(count + 1) / Math.log(max + 1);
  const size = MIN_FONT + scaled * (MAX_FONT - MIN_FONT);
  return `${size.toFixed(3)}rem`;
}

function tagOpacity(count: number, max: number): number {
  if (max === 0) return 1;
  return 0.55 + 0.45 * (count / max);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TagsPage() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('');
  const [sortBy, setSortBy] = useState<'alpha' | 'count'>('count');

  const { data: raw, isLoading, isError } = useQuery<TagsResponse>({
    queryKey: ['tags'],
    queryFn: () => api.listTags() as Promise<TagsResponse>,
    staleTime: 60_000,
  });

  const tags = useMemo<TagEntry[]>(() => {
    if (!raw) return [];
    const entries = normalise(raw);
    const filtered = filter.trim()
      ? entries.filter((e) => e.tag.toLowerCase().includes(filter.trim().toLowerCase()))
      : entries;
    return [...filtered].sort((a, b) =>
      sortBy === 'alpha'
        ? a.tag.localeCompare(b.tag)
        : b.count - a.count
    );
  }, [raw, filter, sortBy]);

  const maxCount = useMemo(() =>
    tags.reduce((m, t) => Math.max(m, t.count), 0),
  [tags]);

  const totalNotes = useMemo(() =>
    normalise(raw ?? []).reduce((s, t) => s + t.count, 0),
  [raw]);

  function handleTagClick(tag: string) {
    navigate(`/notes?tag=${encodeURIComponent(tag)}`);
  }

  // ---- Render --------------------------------------------------------------

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border flex-shrink-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Hash size={18} className="text-text-muted" />
            <h1 className="text-base font-semibold text-text-primary">Tags</h1>
            {!isLoading && raw && (
              <span className="text-xs text-text-faint ml-1">
                {normalise(raw ?? []).length} tags · {totalNotes} note refs
              </span>
            )}
          </div>

          {/* Sort toggle */}
          <button
            onClick={() => setSortBy((s) => s === 'alpha' ? 'count' : 'alpha')}
            className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary transition-colors px-2 py-1 rounded border border-border hover:border-text-faint"
            title={sortBy === 'alpha' ? 'Sorted A–Z (click for by count)' : 'Sorted by count (click for A–Z)'}
          >
            {sortBy === 'alpha' ? <SortAsc size={13} /> : <SortDesc size={13} />}
            {sortBy === 'alpha' ? 'A–Z' : 'By count'}
          </button>
        </div>

        {/* Filter input */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-faint pointer-events-none" />
          <input
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter tags…"
            className="w-full pl-8 pr-3 py-1.5 bg-bg-secondary border border-border rounded text-sm text-text-primary placeholder-text-faint outline-none focus:border-accent-cyan transition-colors"
          />
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto px-6 py-5">

        {/* Skeleton */}
        {isLoading && (
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 24 }).map((_, i) => (
              <div
                key={i}
                className="h-7 rounded-full bg-bg-elevated animate-pulse"
                style={{ width: `${48 + (i % 5) * 20}px` }}
              />
            ))}
          </div>
        )}

        {/* Error */}
        {isError && (
          <div className="flex flex-col items-center justify-center h-40 text-text-muted">
            <Tag size={32} className="mb-3 opacity-30" />
            <p className="text-sm">Could not load tags. Check the backend connection.</p>
          </div>
        )}

        {/* Empty — no tags at all */}
        {!isLoading && !isError && normalise(raw ?? []).length === 0 && (
          <div className="flex flex-col items-center justify-center h-40 text-text-muted">
            <Hash size={40} className="mb-3 opacity-20" />
            <p className="text-sm font-medium">No tags yet</p>
            <p className="text-xs opacity-60 mt-1">Add tags to your notes using the frontmatter <code>tags:</code> field.</p>
          </div>
        )}

        {/* Empty filter result */}
        {!isLoading && !isError && normalise(raw ?? []).length > 0 && tags.length === 0 && (
          <div className="flex flex-col items-center justify-center h-40 text-text-muted">
            <Search size={32} className="mb-3 opacity-30" />
            <p className="text-sm">No tags match <strong className="text-text-primary">{filter}</strong></p>
            <button
              onClick={() => setFilter('')}
              className="mt-2 text-xs text-accent-cyan hover:underline"
            >
              Clear filter
            </button>
          </div>
        )}

        {/* Tag cloud */}
        {!isLoading && tags.length > 0 && (
          <div className="flex flex-wrap gap-x-3 gap-y-2.5 items-baseline">
            {tags.map(({ tag, count }) => (
              <button
                key={tag}
                onClick={() => handleTagClick(tag)}
                title={`${count} note${count !== 1 ? 's' : ''}`}
                style={{
                  fontSize: tagFontSize(count, 1, maxCount),
                  opacity: tagOpacity(count, maxCount),
                }}
                className="group inline-flex items-center gap-1 text-text-primary hover:text-accent-cyan transition-all duration-150 font-medium leading-none"
              >
                <span className="opacity-40 group-hover:opacity-70 transition-opacity text-[0.65em]">#</span>
                {tag}
                <span className="text-[0.65em] text-text-faint group-hover:text-text-muted ml-0.5 transition-colors tabular-nums">
                  {count}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
