import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import { today } from '../lib/dateUtils';
import type { Note } from '../types';

/**
 * DailyNotePage
 * =============
 * Fetches today's daily note and redirects to its editor.
 * Does NOT wrap itself in a QueryClientProvider — the app-level provider
 * (or the test harness wrapper) must supply the QueryClient, which allows
 * tests to control query state and observe the loading indicator.
 */
export default function DailyNotePage() {
  const navigate = useNavigate();
  const dateStr  = today();

  const { data: note, isLoading, isError } = useQuery<Note>({
    queryKey: ['daily', dateStr],
    queryFn:  () => api.getDailyNote(dateStr) as Promise<Note>,
  });

  React.useEffect(() => {
    if (note) {
      navigate(`/notes/${note.note_id ?? (note as { id?: string }).id}`, { replace: true });
    }
  }, [navigate, note]);

  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center h-full animate-spin"
        data-testid="loading"
        style={{ animationDuration: '1s' }}
      >
        <span className="sr-only">Loading daily note…</span>
      </div>
    );
  }

  if (isError || !note) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-gnosis-muted text-sm">Could not load today's note.</p>
        <button
          onClick={() => navigate('/notes/new')}
          className="px-4 py-2 rounded-lg bg-gnosis-accent text-white text-sm"
        >
          Create new note
        </button>
      </div>
    );
  }

  return null;
}
