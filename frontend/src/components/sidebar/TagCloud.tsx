/**
 * TagCloud — sidebar widget showing the vault’s top tags as clickable chips.
 * Clicking a tag navigates to the tags page filtered by that tag.
 */
import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Hash } from 'lucide-react';
import { useNotes } from '../../hooks/useNotes';

const MAX_TAGS = 25;

interface TagEntry {
  tag:   string;
  count: number;
}

/** Build sorted tag frequency table from a flat notes list. */
function buildTagCounts(notes: Array<{ tags?: string[] }>): TagEntry[] {
  const counts: Record<string, number> = {};
  for (const note of notes) {
    for (const tag of note.tags ?? []) {
      counts[tag] = (counts[tag] ?? 0) + 1;
    }
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, MAX_TAGS)
    .map(([tag, count]) => ({ tag, count }));
}

/** Scale font size proportional to tag frequency. */
function fontSize(count: number, max: number): string {
  const minPx = 10;
  const maxPx = 15;
  const ratio = max > 1 ? (count - 1) / (max - 1) : 0;
  return `${(minPx + ratio * (maxPx - minPx)).toFixed(1)}px`;
}

export function TagCloud() {
  const navigate = useNavigate();
  const { data } = useNotes();
  const notes  = data?.items ?? [];
  const tags   = useMemo(() => buildTagCounts(notes), [notes]);
  const maxCnt = tags[0]?.count ?? 1;

  if (tags.length === 0) return null;

  return (
    <div className="px-3 py-2 border-t border-gnosis-border">
      <p className="text-xs font-semibold text-gnosis-muted uppercase tracking-wide mb-2 flex items-center gap-1">
        <Hash size={11} /> Tags
      </p>
      <div className="flex flex-wrap gap-1">
        {tags.map(({ tag, count }) => (
          <button
            key={tag}
            onClick={() => navigate(`/tags?tag=${encodeURIComponent(tag)}`)}
            className="text-gnosis-muted hover:text-gnosis-accent transition-colors leading-none"
            title={`${count} note${count !== 1 ? 's' : ''}`}
            style={{ fontSize: fontSize(count, maxCnt) }}
          >
            #{tag}
          </button>
        ))}
      </div>
    </div>
  );
}
