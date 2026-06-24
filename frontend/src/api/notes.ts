/**
 * api/notes.ts — typed wrappers for the notes + vault endpoints.
 */
import { apiGet, apiPost, apiPut, apiDelete } from './client';
import type { Note, NoteCreate, NoteUpdate } from '../types';

export interface ListNotesParams {
  folder?:    string;
  tag?:       string;
  note_type?: string;
  q?:         string;
  limit?:     number;
  offset?:    number;
}

export async function listNotes(params: ListNotesParams = {}): Promise<Note[]> {
  const qs = new URLSearchParams();
  if (params.folder)    qs.set('folder',    params.folder);
  if (params.tag)       qs.set('tag',        params.tag);
  if (params.note_type) qs.set('note_type',  params.note_type);
  if (params.q)         qs.set('q',          params.q);
  if (params.limit)     qs.set('limit',      String(params.limit));
  if (params.offset)    qs.set('offset',     String(params.offset));
  const query = qs.toString();
  return apiGet<Note[]>(`/notes/${query ? `?${query}` : ''}`);
}

export async function getNote(noteId: string): Promise<Note> {
  return apiGet<Note>(`/notes/${noteId}`);
}

export async function createNote(payload: NoteCreate): Promise<Note> {
  return apiPost<Note>('/notes/', payload);
}

export async function updateNote(noteId: string, payload: NoteUpdate): Promise<Note> {
  return apiPut<Note>(`/notes/${noteId}`, payload);
}

export async function deleteNote(noteId: string): Promise<void> {
  return apiDelete(`/notes/${noteId}`);
}

export async function listTags(): Promise<string[]> {
  return apiGet<string[]>('/notes/tags');
}

export async function listFolders(): Promise<string[]> {
  return apiGet<string[]>('/notes/folders');
}

export async function listTemplates(): Promise<string[]> {
  return apiGet<string[]>('/notes/templates');
}

export async function ingestNote(path: string): Promise<{ job_id: string }> {
  return apiPost<{ job_id: string }>('/notes/ingest', { path });
}

/** Trigger a full vault re-sync. Re-exported here AND from services/api. */
export async function triggerVaultSync(): Promise<{ job_id: string }> {
  return apiPost<{ job_id: string }>('/vault/sync', {});
}
