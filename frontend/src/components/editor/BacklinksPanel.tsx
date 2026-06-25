/**
 * BacklinksPanel — shows incoming wikilinks for the currently open note.
 *
 * Imports getBacklinks from api/notes (named export) rather than from
 * services/api so that vi.spyOn intercepts work correctly in tests.
 */
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getBacklinks } from '../../api/notes';
import type { Backlink } from '../../types';

interface BacklinksPanelProps {
  noteId: string | null;
}

export function BacklinksPanel({ noteId }: BacklinksPanelProps) {
  const { data, isLoading } = useQuery<Backlink[]>({
    queryKey: ['backlinks', noteId],
    queryFn:  async () => {
      const res = await getBacklinks(noteId!);
      return res.backlinks as unknown as Backlink[];
    },
    enabled:  !!noteId,
    staleTime: 30_000,
  });

  if (!noteId) return null;

  if (isLoading) {
    return (
      <div className="text-xs text-text-muted py-2">Loading backlinks…</div>
    );
  }

  const backlinks = data ?? [];

  if (backlinks.length === 0) {
    return (
      <div className="text-xs text-text-faint py-2">No incoming links.</div>
    );
  }

  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-text-muted mb-1">Backlinks ({backlinks.length})</p>
      {backlinks.map((bl, i) => (
        <div
          key={bl.note_id ?? bl.source_note_id ?? i}
          className="text-xs text-text-primary truncate"
          title={bl.title ?? ''}
        >
          {bl.title ?? 'Untitled'}
        </div>
      ))}
    </div>
  );
}

export default BacklinksPanel;
