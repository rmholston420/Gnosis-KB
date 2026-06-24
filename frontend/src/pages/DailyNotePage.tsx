/**
 * DailyNotePage — today’s daily journal note.
 * Fetches or creates the daily note via api.getDailyNote() and
 * opens it in the editor.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import { today } from '../lib/dateUtils';
import type { Note } from '../types';

export default function DailyNotePage() {
  const navigate = useNavigate();
  const dateStr  = today();

  const { data: note, isLoading, isError } = useQuery<Note>({
    queryKey: ['daily', dateStr],
    queryFn:  () => api.getDailyNote(dateStr) as Promise<Note>,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-gnosis-muted text-sm">Loading daily note…</span>
      </div>
    );
  }

  if (isError || !note) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-gnosis-muted text-sm">Could not load today’s note.</p>
        <button
          onClick={() => navigate('/notes/new')}
          className="px-4 py-2 rounded-lg bg-gnosis-accent text-white text-sm"
        >
          Create new note
        </button>
      </div>
    );
  }

  // Redirect to the full note editor
  navigate(`/notes/${note.note_id}`, { replace: true });
  return null;
}
