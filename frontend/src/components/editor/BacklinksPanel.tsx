/**
 * BacklinksPanel — shows incoming backlinks for the active note.
 * noteId is optional (string | null | undefined) — renders empty state
 * when no note is selected.
 */
import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import type { Backlink } from '../../types';

interface BacklinksPanelProps {
  noteId: string | null | undefined;
}

export function BacklinksPanel({ noteId }: BacklinksPanelProps) {
  const { data: backlinks, isLoading } = useQuery({
    queryKey: ['backlinks', noteId],
    queryFn:  () => api.getBacklinks(noteId!) as unknown as Promise<Backlink[]>,
    enabled:  !!noteId,
    staleTime: 30_000,
  });

  if (!noteId) {
    return (
      <div className="p-4 text-xs text-gnosis-muted">
        No note selected.
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-4 text-xs text-gnosis-muted animate-pulse">
        Loading backlinks\u2026
      </div>
    );
  }

  if (!backlinks || backlinks.length === 0) {
    return (
      <div className="p-4 text-xs text-gnosis-muted">
        No backlinks yet.
      </div>
    );
  }

  return (
    <ul className="divide-y divide-gnosis-border">
      {backlinks.map((bl) => (
        <li key={bl.note_id} className="px-4 py-2">
          <p className="text-sm font-medium text-gnosis-fg truncate">{bl.title}</p>
          {bl.context && (
            <p className="text-xs text-gnosis-muted mt-0.5 line-clamp-2">{bl.context}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

export default BacklinksPanel;
