/**
 * AnalyticsPage — vault-level analytics: note type distribution,
 * tag frequency, growth over time, link density.
 */
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { Note, TagRow } from '../types';

type TypeBucket = { note_type: string; count: number };
type TagBucket  = { tag: string; count: number };

export default function AnalyticsPage() {
  const { data: notes } = useQuery({
    queryKey: ['notes', 'all'],
    queryFn:  () =>
      api.listNotes({ page_size: 1000 }).then((r) => (r.items ?? []) as unknown as Note[]),
    staleTime: 60_000,
  });

  const { data: tagRows } = useQuery({
    queryKey: ['tags'],
    queryFn:  () => api.listTags() as unknown as Promise<TagRow[]>,
    staleTime: 60_000,
  });

  // Derive type distribution
  const typeBuckets: TypeBucket[] = React.useMemo(() => {
    if (!notes) return [];
    const counts: Record<string, number> = {};
    notes.forEach((n: Note) => {
      const t = n.note_type ?? 'unknown';
      counts[t] = (counts[t] ?? 0) + 1;
    });
    return Object.entries(counts)
      .map(([note_type, count]) => ({ note_type, count }))
      .sort((a, b) => b.count - a.count);
  }, [notes]);

  // Top tags
  const topTags: TagBucket[] = React.useMemo(() => {
    if (!tagRows) return [];
    return [...tagRows]
      .sort((a: TagRow, b: TagRow) => (b.count ?? 0) - (a.count ?? 0))
      .slice(0, 20)
      .map((t: TagRow) => ({ tag: t.tag ?? String(t), count: t.count ?? 1 }));
  }, [tagRows]);

  const totalNotes   = notes?.length ?? 0;
  const totalWords   = notes?.reduce((acc: number, n: Note) => acc + (n.word_count ?? 0), 0) ?? 0;
  const avgWordCount = totalNotes > 0 ? Math.round(totalWords / totalNotes) : 0;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      <h1 className="text-lg font-semibold text-gnosis-fg">Analytics</h1>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Notes',    value: totalNotes },
          { label: 'Total Words',    value: totalWords.toLocaleString() },
          { label: 'Avg Word Count', value: avgWordCount },
          { label: 'Unique Tags',    value: tagRows?.length ?? 0 },
        ].map(({ label, value }) => (
          <div key={label} className="p-4 rounded-lg bg-gnosis-surface border border-gnosis-border">
            <p className="text-xs text-gnosis-muted">{label}</p>
            <p className="text-xl font-semibold text-gnosis-fg tabular-nums">{value}</p>
          </div>
        ))}
      </div>

      {/* Note type distribution */}
      <section>
        <h2 className="text-sm font-semibold text-gnosis-fg mb-3">Note Types</h2>
        <div className="space-y-2">
          {typeBuckets.map(({ note_type, count }: TypeBucket) => (
            <div key={note_type} className="flex items-center gap-3">
              <span className="w-24 text-xs text-gnosis-muted capitalize">{note_type}</span>
              <div className="flex-1 h-2 bg-gnosis-border rounded-full overflow-hidden">
                <div
                  className="h-full bg-gnosis-accent rounded-full transition-all"
                  style={{ width: `${Math.round((count / totalNotes) * 100)}%` }}
                />
              </div>
              <span className="text-xs text-gnosis-muted tabular-nums w-6 text-right">{count}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Top tags */}
      <section>
        <h2 className="text-sm font-semibold text-gnosis-fg mb-3">Top Tags</h2>
        <div className="flex flex-wrap gap-2">
          {topTags.map(({ tag, count }: TagBucket) => (
            <span
              key={tag}
              className="px-2 py-1 rounded-full bg-gnosis-accent/10 text-gnosis-accent text-xs"
            >
              #{tag} <span className="opacity-60">({count})</span>
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
