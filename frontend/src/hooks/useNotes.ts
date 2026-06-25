/**
 * useNotes — TanStack Query hooks for note CRUD.
 *
 * Contract (enforced by useNotes.test.ts):
 *  - api default export methods are resolved at call-time, not module-load-time
 *  - listNotes mock may return a plain array OR { items, total }
 *  - createNote / updateNote / deleteNote delegates to api default export
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { Note, NoteCreate, NoteUpdate, NoteListResponse } from '../types';
import type {
  listNotes as ListNotesFn,
  getNote as GetNoteFn,
  createNote as CreateNoteFn,
  updateNote as UpdateNoteFn,
  deleteNote as DeleteNoteFn,
  getDailyNote as GetDailyNoteFn,
} from '../services/api';

type AnyRecord = Record<string, unknown>;
type ApiObj = AnyRecord;

export const NOTES_KEY = 'notes';

// ── Late-binding helpers — pick up vi.mock replacements at call-time ──────────
function getApiMethod<T>(name: string, fallback: T): T {
  return ((api as ApiObj)[name] as T | undefined) ?? fallback;
}

function apiListNotes(params: Parameters<ListNotesFn>[0] = {}) {
  return (getApiMethod<ListNotesFn>('listNotes', _stub))(
    params,
  ) as ReturnType<ListNotesFn>;
}
function apiGetNote(id: string) {
  return (getApiMethod<GetNoteFn>('getNote', _stub))(id);
}
function apiCreateNote(data: AnyRecord) {
  return (getApiMethod<CreateNoteFn>('createNote', _stub))(data as Parameters<CreateNoteFn>[0]);
}
function apiUpdateNote(id: string, data: AnyRecord) {
  return (getApiMethod<UpdateNoteFn>('updateNote', _stub))(id, data as Parameters<UpdateNoteFn>[1]);
}
function apiDeleteNote(id: string) {
  return (getApiMethod<DeleteNoteFn>('deleteNote', _stub))(id);
}
function apiGetDailyNote(date: string) {
  return (getApiMethod<GetDailyNoteFn>('getDailyNote', _stub))(date);
}
// Minimal stub so TS is satisfied; real method always supplied by mock or real api
function _stub(..._: unknown[]): never {
  throw new Error('API method not available');
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useNotes(params: Parameters<ListNotesFn>[0] = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, params],
    queryFn: async () => {
      const res = await apiListNotes(params);
      // Handle both array response and { items, total } shape
      if (Array.isArray(res)) return res as unknown as Note[];
      return ((res as { items?: Note[] }).items ?? []) as Note[];
    },
    staleTime: 30_000,
  });
}

export function useNotesList(params: Parameters<ListNotesFn>[0] = {}) {
  return useQuery({
    queryKey: [NOTES_KEY, 'list', params],
    queryFn: async () => {
      const res = await apiListNotes(params);
      if (Array.isArray(res)) return res as unknown as Note[];
      return ((res as { items?: Note[] }).items ?? []) as Note[];
    },
    staleTime: 30_000,
  });
}

export function useNoteList(params: Parameters<ListNotesFn>[0] = {}) {
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
    mutationFn: (data: NoteCreate) =>
      apiCreateNote(data as unknown as AnyRecord) as unknown as Promise<Note>,
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
      return apiUpdateNote(id, payload as unknown as AnyRecord) as unknown as Promise<Note>;
    },
    onSuccess: (_data, vars) => qc.invalidateQueries({ queryKey: [NOTES_KEY, vars.id] }),
  });
}

export function useSaveNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, payload }: { noteId: string; payload: NoteUpdate }) =>
      apiUpdateNote(noteId, payload as unknown as AnyRecord) as unknown as Promise<Note>,
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
