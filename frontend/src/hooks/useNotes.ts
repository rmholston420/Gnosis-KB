/**
 * useNotes hooks — TanStack Query wrappers for the notes REST API.
 *
 * Both canonical names and test-expected aliases are exported.
 */
import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import api from '../services/api';
import type { Note, NoteCreate, NoteUpdate } from '../types';

// ─────────────────────────────────────────────────────────────────────────────
// List
// ─────────────────────────────────────────────────────────────────────────────

export interface ListNotesParams {
  folder?:    string;
  tag?:       string;
  note_type?: string;
  q?:         string;
  limit?:     number;
  offset?:    number;
}

/**
 * Fetch a (filtered) list of notes. Canonical name: useNotes.
 * @param params Optional filters forwarded to GET /api/notes/
 */
export function useNotes(params: ListNotesParams = {}) {
  return useQuery<Note[]>({
    queryKey: ['notes', params],
    queryFn:  () => api.listNotes(params) as Promise<Note[]>,
  });
}

/** Alias expected by unit tests. */
export const useNotesList = useNotes;

// ─────────────────────────────────────────────────────────────────────────────
// Single note
// ─────────────────────────────────────────────────────────────────────────────

export function useNote(noteId: string | null | undefined) {
  return useQuery<Note>({
    queryKey: ['note', noteId],
    queryFn:  () => api.getNote(noteId!) as Promise<Note>,
    enabled:  !!noteId,
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Create
// ─────────────────────────────────────────────────────────────────────────────

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation<Note, Error, NoteCreate>({
    mutationFn: (payload) => api.createNote(payload) as Promise<Note>,
    onSuccess:  () => { void qc.invalidateQueries({ queryKey: ['notes'] }); },
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Update
// ─────────────────────────────────────────────────────────────────────────────

export interface UpdateNoteVars {
  id:      string;
  payload: NoteUpdate;
}

/**
 * Update a note. Canonical usage: `const m = useUpdateNote(); m.mutateAsync({ id, payload });
 * Test-friendly overload: `const m = useUpdateNote(); m.mutateAsync({ id, payload })` — same shape.
 * An optional `noteId` arg is accepted for backward compat with tests that call
 * `useUpdateNote('note-001')` — the argument is ignored; callers must pass id in mutateAsync.
 */
export function useUpdateNote(_noteId?: string) {
  const qc = useQueryClient();
  return useMutation<Note, Error, UpdateNoteVars>({
    mutationFn: ({ id, payload }) => api.updateNote(id, payload) as Promise<Note>,
    onSuccess:  (_, { id }) => {
      void qc.invalidateQueries({ queryKey: ['note', id] });
      void qc.invalidateQueries({ queryKey: ['notes'] });
    },
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Delete
// ─────────────────────────────────────────────────────────────────────────────

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.deleteNote(id),
    onSuccess:  () => {
      void qc.invalidateQueries({ queryKey: ['notes'] });
      void qc.invalidateQueries({ queryKey: ['graph'] });
    },
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Vault-level
// ─────────────────────────────────────────────────────────────────────────────

export function useTags() {
  return useQuery<string[]>({
    queryKey: ['tags'],
    queryFn:  () => api.listTags() as Promise<string[]>,
  });
}

export function useFolders() {
  return useQuery<string[]>({
    queryKey: ['folders'],
    queryFn:  () => api.listFolders() as Promise<string[]>,
  });
}

export function useVaultSync() {
  const qc = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: () => api.triggerVaultSync(),
    onSuccess:  () => {
      void qc.invalidateQueries({ queryKey: ['notes'] });
      void qc.invalidateQueries({ queryKey: ['graph'] });
    },
  });
}
