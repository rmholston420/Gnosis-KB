/**
 * hooks/useNotes.ts — TanStack Query hooks for note data.
 *
 * notesApi.listNotes() returns Note[] directly (no envelope).
 * notesApi.getNote()   returns Note directly.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notesApi } from '../api/notes';
import type { ListNotesParams } from '../api/notes';
import type { Note, NoteCreate, NoteUpdate } from '../types';

export const NOTES_KEY    = 'notes';
export const NOTE_KEY     = 'note';
export const BACKLINK_KEY = 'backlinks';

// ── List ──────────────────────────────────────────────────────────────────────

/** Returns Note[] directly — no envelope. */
export function useNotes(params: ListNotesParams = {}) {
  return useQuery<Note[]>({
    queryKey: [NOTES_KEY, params],
    queryFn:  () => notesApi.listNotes(params),
  });
}

/** Alias kept for any callers that use the old name */
export const useNotesList = useNotes;

// ── Single note ───────────────────────────────────────────────────────────────

export function useNote(id?: string | null) {
  return useQuery<Note>({
    queryKey: [NOTE_KEY, id],
    queryFn:  () => notesApi.getNote(id!),
    enabled:  Boolean(id),
  });
}

// ── Create ────────────────────────────────────────────────────────────────────

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation<Note, Error, NoteCreate>({
    mutationFn: (data) => notesApi.createNote(data),
    onSuccess:  () => qc.invalidateQueries({ queryKey: [NOTES_KEY] }),
  });
}

// ── Update ────────────────────────────────────────────────────────────────────

export function useUpdateNote(id: string) {
  const qc = useQueryClient();
  return useMutation<Note, Error, NoteUpdate>({
    mutationFn: (data) => notesApi.updateNote(id, data),
    onSuccess:  () => {
      qc.invalidateQueries({ queryKey: [NOTE_KEY, id] });
      qc.invalidateQueries({ queryKey: [NOTES_KEY] });
    },
  });
}

// ── Delete ────────────────────────────────────────────────────────────────────

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => notesApi.deleteNote(id),
    onSuccess:  () => qc.invalidateQueries({ queryKey: [NOTES_KEY] }),
  });
}

// ── Backlinks ─────────────────────────────────────────────────────────────────

export function useBacklinks(id?: string | null) {
  return useQuery({
    queryKey: [BACKLINK_KEY, id],
    queryFn:  () => notesApi.getBacklinks(id!),
    enabled:  Boolean(id),
  });
}

// ── Daily note ────────────────────────────────────────────────────────────────

export function useDailyNote(dateStr?: string) {
  return useQuery<Note>({
    queryKey: ['daily-note', dateStr ?? 'today'],
    queryFn:  () => notesApi.getDailyNote(dateStr) as Promise<Note>,
  });
}
