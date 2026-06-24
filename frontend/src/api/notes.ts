/**
 * api/notes.ts — typed API client for note-related endpoints.
 * Exports both the notesApi object AND standalone named functions
 * so pages can do: import { getNote, createNote, ... } from '../api/notes'
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

function normalise(n: Note): Note {
  const id = n.note_id ?? (n as unknown as { id: string }).id;
  return { ...n, note_id: id, id };
}

// ── Object API ────────────────────────────────────────────────────────────────

export const notesApi = {
  listNotes: (params: ListNotesParams = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(
        Object.entries(params)
          .filter(([, v]) => v !== undefined && v !== null)
          .map(([k, v]) => [k, String(v)])
      )
    ).toString();
    return req<Note[]>(`/api/notes${qs ? `?${qs}` : ''}`).then(ns => ns.map(normalise));
  },

  getNote:     (id: string) => req<Note>(`/api/notes/${id}`).then(normalise),
  createNote:  (data: NoteCreate) =>
    req<Note>('/api/notes', { method: 'POST', body: JSON.stringify(data) }).then(normalise),
  updateNote:  (id: string, data: NoteUpdate) =>
    req<Note>(`/api/notes/${id}`, { method: 'PATCH', body: JSON.stringify(data) }).then(normalise),
  deleteNote:  (id: string) => req<void>(`/api/notes/${id}`, { method: 'DELETE' }),
  ingestNote:  (id: string) =>
    req<{ status: string }>(`/api/notes/${id}/ingest`, { method: 'POST' }),
  getBacklinks: (id: string) =>
    req<{ backlinks: Backlink[]; count: number }>(`/api/notes/${id}/backlinks`),
  listTags:    () => req<TagRow[]>('/api/tags'),
  listFolders: () => req<string[]>('/api/folders'),
  listTemplates: () => req<NoteTemplate[]>('/api/templates'),
  triggerVaultSync: () => req<{ status: string }>('/api/vault/sync', { method: 'POST' }),
};

export default notesApi;

// ── Standalone named exports (used by NoteEditorPage destructured imports) ───

export const getNote      = notesApi.getNote;
export const createNote   = notesApi.createNote;
export const updateNote   = notesApi.updateNote;
export const listNotes    = notesApi.listNotes;
export const deleteNote   = notesApi.deleteNote;
