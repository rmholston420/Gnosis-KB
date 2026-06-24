/**
 * hooks/useNotes.ts — TanStack Query hooks for note data.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notesApi } from '../api/notes';
import type { ListNotesParams } from '../api/notes';
import type { Note, NoteCreate, NoteUpdate, Backlink } from '../types';

export const NOTES_KEY  = 'notes';
export const NOTE_KEY   = 'note';
export const BACKLINK_KEY = 'backlinks';

// ── List ──────────────────────────────────────────────────────────────────────

export function useNotes(params: ListNotesParams = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, params],
    queryFn:  () => notesApi.listNotes(params),
  });
}

// ── Single note ───────────────────────────────────────────────────────────────

export function useNote(id: string | null | undefined) {
  return useQuery({
    queryKey:  [NOTE_KEY, id],
    queryFn:   () => notesApi.getNote(id!),
    enabled:   Boolean(id),
  });
}

// ── Backlinks ─────────────────────────────────────────────────────────────────

export function useBacklinks(noteId: string | null | undefined) {
  return useQuery({
    queryKey: [BACKLINK_KEY, noteId],
    queryFn:  () => notesApi.getBacklinks(noteId!),
    enabled:  Boolean(noteId),
    select:   (d): Backlink[] => d.backlinks,
  });
}

// ── Daily note ────────────────────────────────────────────────────────────────

/**
 * Fetches (or creates) today's daily journal note.
 * Returns a query for the note and a mutation to create it if missing.
 */
export function useDailyNote() {
  const qc    = useQueryClient();
  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  const key   = [NOTE_KEY, 'daily', today];

  const query = useQuery({
    queryKey: key,
    queryFn:  () =>
      notesApi.listNotes({ note_type: 'journal', q: today, per_page: 1 })
        .then(ns => ns[0] ?? null),
  });

  const create = useMutation({
    mutationFn: () =>
      notesApi.createNote({
        title:     `Daily Note — ${today}`,
        body:      '',
        note_type: 'journal',
        folder:    'journal',
      }),
    onSuccess: (note) => qc.setQueryData(key, note),
  });

  return { query, create, today };
}

// ── Create / Update / Delete ──────────────────────────────────────────────────

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: NoteCreate) => notesApi.createNote(data),
    onSuccess:  () => qc.invalidateQueries({ queryKey: [NOTES_KEY] }),
  });
}

export function useUpdateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: NoteUpdate }) =>
      notesApi.updateNote(id, data),
    onSuccess:  (note: Note) => {
      qc.setQueryData([NOTE_KEY, note.note_id], note);
      qc.invalidateQueries({ queryKey: [NOTES_KEY] });
    },
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => notesApi.deleteNote(id),
    onSuccess:  () => qc.invalidateQueries({ queryKey: [NOTES_KEY] }),
  });
}
