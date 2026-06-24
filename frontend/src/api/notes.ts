/**
 * api/notes.ts — typed API client for note-related endpoints.
 */
import type {
  Note,
  NoteCreate,
  NoteUpdate,
  TagRow,
  Backlink,
  NoteTemplate,
} from '../types';

export interface ListNotesParams extends Record<string, unknown> {
  folder?: string;
  note_type?: string;
  status?: string;
  tag?: string;
  q?: string;
  page?: number;
  per_page?: number;
  sort?: string;
  order?: 'asc' | 'desc';
}

const BASE = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? '';

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const url = BASE ? `${BASE}${path}` : new URL(path, 'http://localhost').toString();
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function normalise(n: Note): Note {
  const id = n.note_id ?? (n as unknown as { id: string }).id;
  return { ...n, note_id: id, id };
}

export const notesApi = {
  listNotes: (params: ListNotesParams = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(
        Object.entries(params)
          .filter(([, v]) => v !== undefined && v !== null)
          .map(([k, v]) => [k, String(v)]),
      ),
    ).toString();
    return req<Note[]>(`/api/notes${qs ? `?${qs}` : ''}`).then((ns) => ns.map(normalise));
  },

  getNote: (id: string) => req<Note>(`/api/notes/${id}`).then(normalise),
  createNote: (data: NoteCreate) => req<Note>('/api/notes', { method: 'POST', body: JSON.stringify(data) }).then(normalise),
  updateNote: (id: string, data: NoteUpdate) => req<Note>(`/api/notes/${id}`, { method: 'PATCH', body: JSON.stringify(data) }).then(normalise),
  deleteNote: (id: string) => req<void>(`/api/notes/${id}`, { method: 'DELETE' }),
  ingestNote: (id: string) => req<{ status: string }>(`/api/notes/${id}/ingest`, { method: 'POST' }),
  getBacklinks: (id: string) => req<{ backlinks: Backlink[]; count: number }>(`/api/notes/${id}/backlinks`),
  getDailyNote: (dateStr?: string) => {
    const path = dateStr ? `/api/notes/daily?date=${dateStr}` : '/api/notes/daily';
    return req<Note>(path).then(normalise);
  },
  listTags: () => req<TagRow[]>('/api/tags'),
  listFolders: () => req<string[]>('/api/folders'),
  listTemplates: () => req<NoteTemplate[]>('/api/templates'),
};

export const listNotes = notesApi.listNotes;
export const getNote = notesApi.getNote;
export const createNote = notesApi.createNote;
export const updateNote = notesApi.updateNote;
export const deleteNote = notesApi.deleteNote;
export const ingestNote = notesApi.ingestNote;
export const getBacklinks = notesApi.getBacklinks;
export const getDailyNote = notesApi.getDailyNote;
export const listTags = notesApi.listTags;
export const listFolders = notesApi.listFolders;
export const listTemplates = notesApi.listTemplates;

export default notesApi;
