/**
 * useNotes — TanStack Query hooks for note CRUD operations.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as notesApi from '../api/notes';
import type { CreateNotePayload, UpdateNotePayload, ListNotesParams } from '../api/notes';

export const NOTES_KEY = 'notes';

/** List notes with optional filters. */
export function useNotes(params?: ListNotesParams) {
  return useQuery({
    queryKey: [NOTES_KEY, params],
    queryFn:  () => notesApi.listNotes(params),
  });
}

/** Fetch a single note by ID. */
export function useNote(noteId: string | null) {
  return useQuery({
    queryKey: [NOTES_KEY, noteId],
    queryFn:  () => notesApi.getNote(noteId!),
    enabled:  !!noteId,
  });
}

/** Create note mutation — invalidates the notes list. */
export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateNotePayload) => notesApi.createNote(payload),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: [NOTES_KEY] }); },
  });
}

/** Update note mutation. */
export function useUpdateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateNotePayload }) =>
      notesApi.updateNote(id, payload),
    onSuccess: (_data, { id }) => {
      void qc.invalidateQueries({ queryKey: [NOTES_KEY, id] });
      void qc.invalidateQueries({ queryKey: [NOTES_KEY] });
    },
  });
}

/** Delete note mutation. */
export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => notesApi.deleteNote(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: [NOTES_KEY] }); },
  });
}

/** Get today's daily note (auto-created if absent). */
export function useDailyNote() {
  return useQuery({
    queryKey: [NOTES_KEY, 'daily'],
    queryFn:  () => notesApi.getDailyNote(),
  });
}

/** Get orphaned notes. */
export function useOrphans() {
  return useQuery({
    queryKey: [NOTES_KEY, 'orphans'],
    queryFn:  () => notesApi.getOrphans(),
  });
}

/** Get backlinks for a note. */
export function useBacklinks(noteId: string | null) {
  return useQuery({
    queryKey: [NOTES_KEY, noteId, 'backlinks'],
    queryFn:  () => notesApi.getBacklinks(noteId!),
    enabled:  !!noteId,
  });
}
