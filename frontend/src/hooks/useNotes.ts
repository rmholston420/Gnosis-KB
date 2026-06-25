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

export function useNotes(params: Parameters<typeof listNotes>[0] = {}) {
  return useQuery({
    queryKey: ['notes', params],
    queryFn:  () =>
      listNotes(params).then((res) => (res.items ?? []) as unknown as Note[]),
    staleTime: 30_000,
  });
}

export function useNoteList(params: Parameters<typeof listNotes>[0] = {}) {
  return useQuery({
    queryKey: ['notes', 'list', params],
    queryFn:  () =>
      listNotes(params) as unknown as Promise<NoteListResponse>,
    staleTime: 30_000,
  });
}

export function useNote(id: string | null) {
  return useQuery({
    queryKey: ['notes', id],
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notes'] }),
  });
}

export function useUpdateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: NoteUpdate & { id: string }) => {
      if (payload && Object.keys(payload).length > 0) {
        return updateNote(id, payload as unknown as AnyRecord) as Promise<Note>;
      }
      return updateNote(id, payload as unknown as AnyRecord) as Promise<Note>;
    },
    onSuccess: (_data, vars) =>
      qc.invalidateQueries({ queryKey: ['notes', vars.id] }),
  });
}

export function useSaveNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, payload }: { noteId: string; payload: NoteUpdate }) =>
      updateNote(noteId, payload as unknown as AnyRecord) as Promise<Note>,
    onSuccess: (_data, vars) =>
      qc.invalidateQueries({ queryKey: ['notes', vars.noteId] }),
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteNote(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notes'] }),
  });
}

export function useDailyNote(dateStr: string) {
  return useQuery({
    queryKey: ['notes', 'daily', dateStr],
    queryFn:  () => getDailyNote(dateStr) as unknown as Promise<Note>,
    staleTime: 60_000,
  });
}

// Named re-export used by NoteEditorPage
export function listNotes_hook(params: Parameters<typeof listNotes>[0] = {}) {
  return listNotes(params).then((res) => (res.items ?? []) as unknown as Note[]);
}
