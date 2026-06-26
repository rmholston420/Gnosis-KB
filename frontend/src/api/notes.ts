/**
 * api/notes.ts — typed API client for note-related endpoints.
 *
 * FIXES:
 *  - req() now injects Bearer token from localStorage (was missing entirely)
 *  - BASE reads VITE_API_BASE_URL (was VITE_API_URL — wrong env var, produced /api/notes
 *    instead of /api/v1/notes, causing 404 on every call in production)
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

// FIX: was VITE_API_URL (always empty string) — must match services/api.ts
const BASE =
  (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_BASE_URL ?? '/api/v1';

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  // FIX: inject auth token — was completely missing, causing 401 on all calls
  const token =
    typeof localStorage !== 'undefined' ? localStorage.getItem('gnosis_token') : null;
  const authHeader: Record<string, string> = token
    ? { Authorization: `Bearer ${token}` }
    : {};

  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeader,
    },
    ...init,
    // ensure our headers win if init also sets headers
    ...(init?.headers
      ? { headers: { 'Content-Type': 'application/json', ...authHeader, ...init.headers } }
      : {}),
  });

  // FIX: 401 → clear stale token and redirect to login
  if (res.status === 401) {
    if (typeof localStorage !== 'undefined') localStorage.removeItem('gnosis_token');
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new Error('Unauthorized');
  }

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
    return req<Note[]>(`/notes/${qs ? `?${qs}` : ''}`).then((ns) => ns.map(normalise));
  },

  getNote: (id: string) => req<Note>(`/notes/${id}`).then(normalise),
  createNote: (data: NoteCreate) =>
    req<Note>('/notes/', { method: 'POST', body: JSON.stringify(data) }).then(normalise),
  updateNote: (id: string, data: NoteUpdate) =>
    req<Note>(`/notes/${id}`, { method: 'PATCH', body: JSON.stringify(data) }).then(normalise),
  deleteNote: (id: string) => req<void>(`/notes/${id}`, { method: 'DELETE' }),
  ingestNote: (id: string) =>
    req<{ status: string }>(`/notes/${id}/ingest`, { method: 'POST' }),
  getBacklinks: (id: string) =>
    req<{ backlinks: Backlink[]; count: number }>(`/notes/${id}/backlinks`),
  getDailyNote: (dateStr?: string) => {
    const path = dateStr ? `/notes/daily?date=${dateStr}` : '/notes/daily';
    return req<Note>(path).then(normalise);
  },
  listTags: () => req<TagRow[]>('/tags/'),
  listFolders: () => req<string[]>('/notes/folders'),
  listTemplates: () => req<NoteTemplate[]>('/notes/templates'),
};

export const listNotes    = notesApi.listNotes;
export const getNote      = notesApi.getNote;
export const createNote   = notesApi.createNote;
export const updateNote   = notesApi.updateNote;
export const deleteNote   = notesApi.deleteNote;
export const ingestNote   = notesApi.ingestNote;
export const getBacklinks = notesApi.getBacklinks;
export const getDailyNote = notesApi.getDailyNote;
export const listTags     = notesApi.listTags;
export const listFolders  = notesApi.listFolders;
export const listTemplates = notesApi.listTemplates;

export default notesApi;
