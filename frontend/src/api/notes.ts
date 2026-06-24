/**
 * api/notes.ts — typed API client for note-related endpoints.
 */
import type {
  Note,
  NoteCreate,
  NoteUpdate,
  TagRow,
  Backlink,
} from '../types';

export interface ListNotesParams extends Record<string, unknown> {
  folder?:    string;
  note_type?: string;
  status?:    string;
  tag?:       string;
  q?:         string;
  page?:      number;
  per_page?:  number;
  sort?:      string;
  order?:     'asc' | 'desc';
}

const BASE = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? '';

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

/** Normalise a raw note so `note.id` always equals `note.note_id`. */
function normalise(n: Note): Note {
  return { ...n, id: n.note_id ?? (n as unknown as { id: string }).id };
}

export const notesApi = {
  listNotes:   (params: ListNotesParams = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(
        Object.entries(params)
          .filter(([, v]) => v !== undefined && v !== null)
          .map(([k, v]) => [k, String(v)])
      )
    ).toString();
    return req<Note[]>(`/api/notes${qs ? `?${qs}` : ''}`).then(ns => ns.map(normalise));
  },

  getNote:     (id: string) =>
    req<Note>(`/api/notes/${id}`).then(normalise),

  createNote:  (data: NoteCreate) =>
    req<Note>('/api/notes', { method: 'POST', body: JSON.stringify(data) }).then(normalise),

  updateNote:  (id: string, data: NoteUpdate) =>
    req<Note>(`/api/notes/${id}`, { method: 'PATCH', body: JSON.stringify(data) }).then(normalise),

  deleteNote:  (id: string) =>
    req<void>(`/api/notes/${id}`, { method: 'DELETE' }),

  ingestNote:  (id: string) =>
    req<{ status: string }>(`/api/notes/${id}/ingest`, { method: 'POST' }),

  /** Returns backlinks for a given note. */
  getBacklinks: (id: string) =>
    req<{ backlinks: Backlink[]; count: number }>(`/api/notes/${id}/backlinks`),

  /** List all tags with usage counts. */
  listTags:    () => req<TagRow[]>('/api/tags'),

  listFolders:    () => req<string[]>('/api/folders'),
  listTemplates:  () => req<string[]>('/api/templates'),
  triggerVaultSync: () => req<{ status: string }>('/api/vault/sync', { method: 'POST' }),
};

export default notesApi;
