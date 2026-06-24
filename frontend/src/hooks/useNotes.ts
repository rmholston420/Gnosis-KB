/**
 * hooks/useNotes.ts — TanStack Query hooks for note data.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import { getBacklinks } from '../api/notes';
import type { ListNotesParams } from '../api/notes';
import type { Note, NoteCreate, NoteUpdate } from '../types';

export const NOTES_KEY = 'notes';
export const NOTE_KEY = 'note';
export const BACKLINK_KEY = 'backlinks';

export function useNotes(params: ListNotesParams = {}) {
  return useQuery<Note[]>({
    queryKey: [NOTES_KEY, params],
    queryFn: () => api.listNotes(params) as Promise<Note[]>,
  });
}

export const useNotesList = useNotes;

export function useNote(id?: string | null) {
  return useQuery<Note>({
    queryKey: [NOTE_KEY, id],
    queryFn: () => api.getNote(id!) as Promise<Note>,
    enabled: Boolean(id),
  });
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation<Note, Error, NoteCreate>({
    mutationFn: (data) => api.createNote(data) as Promise<Note>,
    onSuccess: () => qc.invalidateQueries({ queryKey: [NOTES_KEY] }),
  });
}

export function useUpdateNote(id?: string) {
  const qc = useQueryClient();
  return useMutation<Note, Error, NoteUpdate | { id: string; payload: NoteUpdate }>({
    mutationFn: (data) => {
      if (id !== undefined) {
        if ('id' in (data as { id?: string })) {
          const payload = (data as { payload?: NoteUpdate }).payload ?? {};
          return api.updateNote(id, payload) as Promise<Note>;
        }
        return api.updateNote(id, data as NoteUpdate) as Promise<Note>;
      }
      const { id: noteId, payload } = data as { id: string; payload: NoteUpdate };
      return api.updateNote(noteId, payload) as Promise<Note>;
    },
    onSuccess: (_note, data) => {
      const resolvedId = id ?? (data as { id?: string }).id;
      if (resolvedId) qc.invalidateQueries({ queryKey: [NOTE_KEY, resolvedId] });
      qc.invalidateQueries({ queryKey: [NOTES_KEY] });
    },
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.deleteNote(id) as Promise<void>,
    onSuccess: () => qc.invalidateQueries({ queryKey: [NOTES_KEY] }),
  });
}

export function useBacklinks(id?: string | null) {
  return useQuery({
    queryKey: [BACKLINK_KEY, id],
    queryFn: () => getBacklinks(id!),
    enabled: Boolean(id),
  });
}

export function useDailyNote(dateStr?: string) {
  return useQuery<Note>({
    queryKey: ['daily-note', dateStr ?? 'today'],
    queryFn: () => api.getDailyNote(dateStr) as Promise<Note>,
  });
}
