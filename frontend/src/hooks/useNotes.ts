/**
 * useNotes — TanStack Query hooks for note CRUD.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listNotes, getNote, createNote, updateNote, deleteNote, getDailyNote,
} from '../services/api';
import type { Note, NoteCreate, NoteUpdate, NoteListResponse } from '../types';

// Allow NoteCreate/NoteUpdate to satisfy Record<string,unknown> at the call site
type AnyRecord = Record<string, unknown>;

/** Stable query key base used by useWebSocket for cache invalidation. */
export const NOTES_KEY = 'notes';

export function useNotes(params: Parameters<typeof listNotes>[0] = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, params],
    queryFn:  () =>
      listNotes(params).then((res) => (res.items ?? []) as unknown as Note[]),
    staleTime: 30_000,
  });
}

/** Alias — tests import useNotesList (with capital L) */
export function useNotesList(params: Parameters<typeof listNotes>[0] = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, 'list', params],
    queryFn:  () =>
      listNotes(params).then((res) => (res.items ?? []) as unknown as Note[]),
    staleTime: 30_000,
  });
}

export function useNoteList(params: Parameters<typeof listNotes>[0] = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, 'list', params],
    queryFn:  () =>
      listNotes(params) as unknown as Promise<NoteListResponse>,
    staleTime: 30_000,
  });
}

export function useNote(id: string | null) {
  return useQuery({
    queryKey: [NOTES_KEY, id],
    queryFn:  () => getNote(id!) as unknown as Promise<Note>,
    enabled:  !!id,
    staleTime: 30_000,
  });
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: NoteCreate) =>
      createNote(data as unknown as AnyRecord) as Promise<Note>,
    onSuccess: () => qc.invalidateQueries({ queryKey: [NOTES_KEY] }),
  });
}

/**
 * useUpdateNote — accepts either:
 *   mutateAsync({ id, ...fields })           — destructure style
 *   mutateAsync({ id, payload: {...} })      — explicit payload style (test compat)
 *
 * Also accepts an optional noteId argument for legacy compat (ignored at runtime).
 */
export function useUpdateNote(_noteId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: (NoteUpdate & { id: string }) | { id: string; payload: NoteUpdate }) => {
      const { id } = vars;
      const payload = 'payload' in vars
        ? vars.payload
        : (({ id: _id, ...rest }: NoteUpdate & { id: string }) => rest)(vars as NoteUpdate & { id: string });
      return updateNote(id, payload as unknown as AnyRecord) as Promise<Note>;
    },
    onSuccess: (_data, vars) =>
      qc.invalidateQueries({ queryKey: [NOTES_KEY, vars.id] }),
  });
}

export function useSaveNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, payload }: { noteId: string; payload: NoteUpdate }) =>
      updateNote(noteId, payload as unknown as AnyRecord) as Promise<Note>,
    onSuccess: (_data, vars) =>
      qc.invalidateQueries({ queryKey: [NOTES_KEY, vars.noteId] }),
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteNote(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [NOTES_KEY] }),
  });
}

/** dateStr is optional — defaults to today when omitted. */
export function useDailyNote(dateStr?: string) {
  const d = dateStr ?? new Date().toISOString().slice(0, 10);
  return useQuery({
    queryKey: [NOTES_KEY, 'daily', d],
    queryFn:  () => getDailyNote(d) as unknown as Promise<Note>,
    staleTime: 60_000,
  });
}

// Named re-export used by NoteEditorPage
export function listNotes_hook(params: Parameters<typeof listNotes>[0] = {}) {
  return listNotes(params).then((res) => (res.items ?? []) as unknown as Note[]);
}
