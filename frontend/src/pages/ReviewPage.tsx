/**
 * ReviewPage — spaced-repetition review queue.
 * Fetches notes flagged for review and presents them sequentially.
 */
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import { NoteCard } from '../components/NoteCard';
import type { Note } from '../types';

export default function ReviewPage() {
  const qc = useQueryClient();
  const [idx, setIdx] = useState(0);

  const { data: notes = [], isLoading } = useQuery<Note[]>({
    queryKey: ['notes', 'review'],
    queryFn:  () => api.listNotes({ tag: 'review', limit: 200 }) as Promise<Note[]>,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      api.updateNote(id, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notes'] });
      setIdx((i) => Math.min(i + 1, notes.length - 1));
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-gnosis-muted text-sm">Loading review queue…</span>
      </div>
    );
  }

  if (!notes.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2">
        <p className="text-gnosis-fg font-medium">No notes to review — great work!</p>
        <p className="text-gnosis-muted text-sm">Tag a note with #review to add it here.</p>
      </div>
    );
  }

  const current = notes[idx];

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-gnosis-fg">Review</h1>
        <span className="text-sm text-gnosis-muted">{idx + 1} / {notes.length}</span>
      </div>

      {current && (
        <>
          <NoteCard note={current} />

          <div className="flex gap-3 mt-6">
            <button
              onClick={() => setIdx((i) => Math.max(i - 1, 0))}
              disabled={idx === 0}
              className="flex-1 py-2 rounded-lg border border-gnosis-border text-sm text-gnosis-muted hover:bg-gnosis-hover disabled:opacity-40"
            >
              ← Previous
            </button>
            <button
              onClick={() =>
                updateMutation.mutate({
                  id: current.note_id,
                  payload: { frontmatter: { reviewed_at: new Date().toISOString() } },
                })
              }
              className="flex-1 py-2 rounded-lg bg-gnosis-accent text-white text-sm font-medium hover:opacity-90"
            >
              Mark reviewed
            </button>
            <button
              onClick={() => setIdx((i) => Math.min(i + 1, notes.length - 1))}
              disabled={idx === notes.length - 1}
              className="flex-1 py-2 rounded-lg border border-gnosis-border text-sm text-gnosis-muted hover:bg-gnosis-hover disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  );
}
