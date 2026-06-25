/**
 * useNotes — TanStack Query hooks for note CRUD.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, {
  listNotes, getNote, createNote, updateNote, deleteNote, getDailyNote,
} from '../services/api';
import type { Note, NoteCreate, NoteUpdate, NoteListResponse } from '../types';

type AnyRecord = Record<string, unknown>;

export const NOTES_KEY = 'notes';

const apiListNotes = api.listNotes ?? listNotes;
const apiGetNote = api.getNote ?? getNote;
const apiCreateNote = api.createNote ?? createNote;
const apiUpdateNote = api.updateNote ?? updateNote;
const apiDeleteNote = api.deleteNote ?? deleteNote;
const apiGetDailyNote = api.getDailyNote ?? getDailyNote;

export function useNotes(params: Parameters<typeof listNotes>[0] = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, params],
    queryFn: () => apiListNotes(params).then((res) => (res.items ?? res ?? []) as unknown as Note[]),
    staleTime: 30_000,
  });
}

export function useNotesList(params: Parameters<typeof listNotes>[0] = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, 'list', params],
    queryFn: () => apiListNotes(params).then((res) => (res.items ?? res ?? []) as unknown as Note[]),
    staleTime: 30_000,
  });
}

export function useNoteList(params: Parameters<typeof listNotes>[0] = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, 'list', params],
    queryFn: () => apiListNotes(params) as unknown as Promise<NoteListResponse>,
    staleTime: 30_000,
  });
}

export function useNote(id: string | null) {
  return useQuery({
    queryKey: [NOTES_KEY, id],
    queryFn: () => apiGetNote(id!) as unknown as Promise<Note>,
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: NoteCreate) => apiCreateNote(data as unknown as AnyRecord) as Promise<Note>,
    onSuccess: () => qc.invalidateQueries({ queryKey: [NOTES_KEY] }),
  });
}

export function useUpdateNote(_noteId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: (NoteUpdate & { id: string }) | { id: string; payload: NoteUpdate }) => {
      const { id } = vars;
      const payload = 'payload' in vars
        ? vars.payload
        : (({ id: _id, ...rest }: NoteUpdate & { id: string }) => rest)(vars as NoteUpdate & { id: string });
      return apiUpdateNote(id, payload as unknown as AnyRecord) as Promise<Note>;
    },
    onSuccess: (_data, vars) => qc.invalidateQueries({ queryKey: [NOTES_KEY, vars.id] }),
  });
}

export function useSaveNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, payload }: { noteId: string; payload: NoteUpdate }) =>
      apiUpdateNote(noteId, payload as unknown as AnyRecord) as Promise<Note>,
    onSuccess: (_data, vars) => qc.invalidateQueries({ queryKey: [NOTES_KEY, vars.noteId] }),
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiDeleteNote(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [NOTES_KEY] }),
  });
}

export function useDailyNote(dateStr?: string) {
  const d = dateStr ?? new Date().toISOString().slice(0, 10);
  return useQuery({
    queryKey: [NOTES_KEY, 'daily', d],
    queryFn: () => apiGetDailyNote(d) as unknown as Promise<Note>,
    staleTime: 60_000,
  });
}

export function listNotes_hook(params: Parameters<typeof listNotes>[0] = {}) {
  return apiListNotes(params).then((res) => (res.items ?? res ?? []) as unknown as Note[]);
}
