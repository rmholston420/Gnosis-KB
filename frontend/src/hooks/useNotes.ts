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

// Resolve API functions at call-time (not module load-time) so test mocks
// that only partially stub the default export don't throw at import.
function getApiListNotes() { return (api as AnyRecord).listNotes as typeof listNotes ?? listNotes; }
function getApiGetNote() { return (api as AnyRecord).getNote as typeof getNote ?? getNote; }
function getApiCreateNote() { return (api as AnyRecord).createNote as typeof createNote ?? createNote; }
function getApiUpdateNote() { return (api as AnyRecord).updateNote as typeof updateNote ?? updateNote; }
function getApiDeleteNote() { return (api as AnyRecord).deleteNote as typeof deleteNote ?? deleteNote; }
function getApiGetDailyNote() {
  const fn = (api as AnyRecord).getDailyNote as typeof getDailyNote | undefined;
  return fn ?? getDailyNote;
}

export function useNotes(params: Parameters<typeof listNotes>[0] = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, params],
    queryFn: () => getApiListNotes()(params).then((res) => (res.items ?? res ?? []) as unknown as Note[]),
    staleTime: 30_000,
  });
}

export function useNotesList(params: Parameters<typeof listNotes>[0] = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, 'list', params],
    queryFn: () => getApiListNotes()(params).then((res) => (res.items ?? res ?? []) as unknown as Note[]),
    staleTime: 30_000,
  });
}

export function useNoteList(params: Parameters<typeof listNotes>[0] = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, 'list', params],
    queryFn: () => getApiListNotes()(params) as unknown as Promise<NoteListResponse>,
    staleTime: 30_000,
  });
}

export function useNote(id: string | null) {
  return useQuery({
    queryKey: [NOTES_KEY, id],
    queryFn: () => getApiGetNote()(id!) as unknown as Promise<Note>,
    enabled: !!id,
    staleTime: 30_000,
  });
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: NoteCreate) => getApiCreateNote()(data as unknown as AnyRecord) as Promise<Note>,
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
      return getApiUpdateNote()(id, payload as unknown as AnyRecord) as Promise<Note>;
    },
    onSuccess: (_data, vars) => qc.invalidateQueries({ queryKey: [NOTES_KEY, vars.id] }),
  });
}

export function useSaveNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, payload }: { noteId: string; payload: NoteUpdate }) =>
      getApiUpdateNote()(noteId, payload as unknown as AnyRecord) as Promise<Note>,
    onSuccess: (_data, vars) => qc.invalidateQueries({ queryKey: [NOTES_KEY, vars.noteId] }),
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => getApiDeleteNote()(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [NOTES_KEY] }),
  });
}

export function useDailyNote(dateStr?: string) {
  const d = dateStr ?? new Date().toISOString().slice(0, 10);
  return useQuery({
    queryKey: [NOTES_KEY, 'daily', d],
    queryFn: () => getApiGetDailyNote()(d) as unknown as Promise<Note>,
    staleTime: 60_000,
  });
}

export function listNotes_hook(params: Parameters<typeof listNotes>[0] = {}) {
  return getApiListNotes()(params).then((res) => (res.items ?? res ?? []) as unknown as Note[]);
}
