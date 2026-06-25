/**
 * BacklinksPanel — sidebar panel listing notes that link to the current note.
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import type { Note, LinkRef } from '../../types';

interface BacklinksPanelProps {
  noteId: string;
}

interface BacklinkEntry {
  note_id: string;
  title:   string;
  excerpt?: string;
}

export function BacklinksPanel({ noteId }: BacklinksPanelProps) {
  const { data: note, isLoading } = useQuery({
    queryKey: ['note', noteId],
    queryFn:  () => api.getNote(noteId) as unknown as Promise<Note>,
    staleTime: 30_000,
  });

  const backlinks: LinkRef[] = (note as Note | undefined)?.incoming_links ?? [];

  if (isLoading) {
    return (
      <div className="p-4 text-xs text-gnosis-muted animate-pulse">
        Loading backlinks…
      </div>
    );
  }

  if (backlinks.length === 0) {
    return (
      <div className="p-4 text-xs text-gnosis-muted">
        No backlinks found.
      </div>
    );
  }

  return (
    <div className="p-2 space-y-1">
      <p className="text-xs font-semibold text-gnosis-muted uppercase tracking-wide px-1 mb-2">
        Backlinks ({backlinks.length})
      </p>
      {backlinks.map((bl: LinkRef) => (
        <Link
          key={bl.note_id}
          to={`/notes/${bl.note_id}`}
          className="block px-2 py-1.5 rounded hover:bg-gnosis-border text-xs text-gnosis-fg transition-colors"
        >
          <span className="font-medium">{bl.title}</span>
          {bl.excerpt && (
            <span className="block text-gnosis-muted mt-0.5 line-clamp-1">{bl.excerpt}</span>
          )}
        </Link>
      ))}
    </div>
  );
}

export type { BacklinkEntry };
